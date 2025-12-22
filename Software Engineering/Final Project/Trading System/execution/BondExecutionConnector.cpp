/**
 * BondExecutionConnector.cpp
 * Implementation of outbound connector that publishes executions to a TCP subscriber.
 *
 * @author Hao Wang
 */

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

using namespace std;

BondExecutionConnector::BondExecutionConnector(int p) : port(p) {}

/**
 * Send the full buffer even if send() only transmits partial bytes each call.
 *
 * @param sock TCP socket fd.
 * @param data Buffer pointer.
 * @param len  Buffer length.
 * @return true if all bytes sent successfully.
 */
static bool SendAll(int sock, const char* data, size_t len)
{
    size_t sent = 0;
    while (sent < len)
    {
        // send() can be interrupted or can send fewer bytes than requested.
        ssize_t n = send(sock, data + sent, len - sent, 0);
        if (n < 0)
        {
            if (errno == EINTR) continue; // retry on interrupt
            return false;
        }
        if (n == 0) return false; // peer closed unexpectedly

        sent += static_cast<size_t>(n);
    }
    return true;
}

void BondExecutionConnector::Publish(ExecutionOrder<Bond>& data)
{
    // Create client socket to external subscriber.
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0)
    {
        cerr << "[ExecutionConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    sockaddr_in serv{};
    serv.sin_family = AF_INET;
    serv.sin_port = htons(port);

    // Connect to local machine (loopback).
    if (inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr) != 1)
    {
        cerr << "[ExecutionConnector] inet_pton() failed\n";
        close(sock);
        return;
    }

    if (connect(sock, (sockaddr*)&serv, sizeof(serv)) < 0)
    {
        cerr << "[ExecutionConnector] connect() failed: " << strerror(errno) << "\n";
        close(sock);
        return;
    }

    // Build newline-delimited message for streaming receiver.
    stringstream ss;
    ss << "EXEC,"
        << data.GetProduct().GetProductId() << ","
        << data.GetOrderId() << ","
        << data.GetPrice() << ","
        << data.GetVisibleQuantity()
        << "\n";

    const string msg = ss.str();

    if (!SendAll(sock, msg.c_str(), msg.size()))
    {
        cerr << "[ExecutionConnector] send() failed: " << strerror(errno) << "\n";
    }

    close(sock);
}
