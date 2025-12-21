// ====================== BondStreamingConnector.cpp ======================
#include "BondStreamingConnector.hpp"

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

BondStreamingConnector::BondStreamingConnector(int p)
    : port(p)
{
}

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

void BondStreamingConnector::Publish(PriceStream<Bond>& data)
{
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0)
    {
        std::cerr << "[StreamingConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    sockaddr_in serv{};
    serv.sin_family = AF_INET;
    serv.sin_port = htons(port);

    if (inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr) != 1)
    {
        std::cerr << "[StreamingConnector] inet_pton() failed\n";
        close(sock);
        return;
    }

    if (connect(sock, (struct sockaddr*)&serv, sizeof(serv)) < 0)
    {
        std::cerr << "[StreamingConnector] connect() failed: " << strerror(errno) << "\n";
        close(sock);
        return;
    }

    // Message format:
    // STREAM,cusip,bidPx,askPx,bidQty,askQty\n
    std::stringstream ss;
    ss << "STREAM,"
        << data.GetProduct().GetProductId() << ","
        << data.GetBidOrder().GetPrice() << ","
        << data.GetOfferOrder().GetPrice() << ","
        << data.GetBidOrder().GetVisibleQuantity() << ","
        << data.GetOfferOrder().GetVisibleQuantity()
        << "\n";

    const string msg = ss.str();

    if (!SendAll(sock, msg.c_str(), msg.size()))
    {
        std::cerr << "[StreamingConnector] send() failed: " << strerror(errno) << "\n";
        // still close socket
    }

    close(sock);
}
