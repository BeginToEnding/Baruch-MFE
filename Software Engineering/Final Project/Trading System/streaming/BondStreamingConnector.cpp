/**
 * BondStreamingConnector.cpp
 * Implements the outbound connector for streaming quotes.
 *
 * @author Hao Wang
 */

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

using namespace std;

BondStreamingConnector::BondStreamingConnector(int p)
    : port(p)
{
}

/**
 * Send the full buffer even if send() only transmits partial bytes.
 */
static bool SendAll(int sock, const char* data, size_t len)
{
    size_t sent = 0;
    while (sent < len)
    {
        ssize_t n = send(sock, data + sent, len - sent, 0);
        if (n < 0)
        {
            if (errno == EINTR) continue; // retry on interrupt
            return false;
        }
        if (n == 0) return false;
        sent += static_cast<size_t>(n);
    }
    return true;
}

void BondStreamingConnector::Publish(PriceStream<Bond>& data)
{
    // Create a client socket to the external subscriber.
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0)
    {
        cerr << "[StreamingConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    sockaddr_in serv{};
    serv.sin_family = AF_INET;
    serv.sin_port = htons(port);

    // Connect to localhost (loopback).
    if (inet_pton(AF_INET, "127.0.0.1", &serv.sin_addr) != 1)
    {
        cerr << "[StreamingConnector] inet_pton() failed\n";
        close(sock);
        return;
    }

    if (connect(sock, (sockaddr*)&serv, sizeof(serv)) < 0)
    {
        cerr << "[StreamingConnector] connect() failed: " << strerror(errno) << "\n";
        close(sock);
        return;
    }

    // Build message in a simple CSV line. Newline is required for stream framing.
    stringstream ss;
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
        cerr << "[StreamingConnector] send() failed: " << strerror(errno) << "\n";
    }

    close(sock);
}
