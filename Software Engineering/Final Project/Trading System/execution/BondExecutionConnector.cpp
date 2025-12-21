// ====================== BondExecutionConnector.cpp ======================
#include "BondExecutionConnector.hpp"

#include <sstream>
#include <iostream>
#include <string>
#include <cerrno>
#include <cstring>

// POSIX sockets (WSL/Linux)
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>

using std::string;

BondExecutionConnector::BondExecutionConnector(int p) : port(p) {}

static bool SendAll(int sock, const char* data, size_t len)
{
    size_t sent = 0;
    while (sent < len)
    {
        ssize_t n = send(sock, data + sent, len - sent, 0);
        if (n <= 0) return false;
        sent += static_cast<size_t>(n);
    }
    return true;
}

void BondExecutionConnector::Publish(ExecutionOrder<Bond>& data)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0)
    {
        std::cerr << "[ExecutionConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    sockaddr_in serv{};
    serv.sin_family = AF_INET;
    serv.sin_port = htons(port);

    // 127.0.0.1 in network byte order
    if (inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr) != 1)
    {
        std::cerr << "[ExecutionConnector] inet_pton() failed\n";
        close(sock);
        return;
    }

    if (connect(sock, (struct sockaddr*)&serv, sizeof(serv)) < 0)
    {
        std::cerr << "[ExecutionConnector] connect() failed: " << strerror(errno) << "\n";
        close(sock);
        return;
    }

    std::stringstream ss;
    ss << "EXEC,"
        << data.GetProduct().GetProductId() << ","
        << data.GetOrderId() << ","
        << data.GetPrice() << ","
        << data.GetVisibleQuantity()
        << "\n"; // newline delimiter for receiver

    const string msg = ss.str();

    if (!SendAll(sock, msg.c_str(), msg.size()))
    {
        std::cerr << "[ExecutionConnector] send() failed: " << strerror(errno) << "\n";
        // fall through and close
    }

    close(sock);
}
