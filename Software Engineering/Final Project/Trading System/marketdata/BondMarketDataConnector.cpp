/**
 * BondMarketDataConnector.cpp
 * Implementation of the inbound market data connector.
 *
 * @author Hao Wang
 */

#include "BondMarketDataConnector.hpp"
#include "../utils/PriceUtils.hpp"

#include <sstream>
#include <iostream>
#include <string>
#include <cerrno>
#include <cstring>

 // POSIX sockets (WSL/Linux)
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>

using namespace std;

BondMarketDataConnector::BondMarketDataConnector(BondMarketDataService* s, int p)
    : service(s), port(p) {}

/**
 * Remove trailing '\r' so CRLF lines are accepted.
 */
static inline void TrimCR(string& s)
{
    if (!s.empty() && s.back() == '\r') s.pop_back();
}

void BondMarketDataConnector::Start()
{
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
    {
        cerr << "[MarketDataConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        cerr << "[MarketDataConnector] setsockopt() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (sockaddr*)&address, sizeof(address)) < 0)
    {
        cerr << "[MarketDataConnector] bind() failed on port " << port
            << ": " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    if (listen(server_fd, 128) < 0)
    {
        cerr << "[MarketDataConnector] listen() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    cout << "[MarketDataConnector] Listening on port " << port << endl;

    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (sockaddr*)&address, &addrlen);
        if (client_fd < 0)
        {
            cerr << "[MarketDataConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        // A single client connection can stream many messages.
        string pending;
        char buffer[4096];

        while (true)
        {
            // TCP framing: one read() can contain partial or multiple lines.
            ssize_t n = read(client_fd, buffer, sizeof(buffer));
            if (n == 0) break; // client closed
            if (n < 0)
            {
                if (errno == EINTR) continue; // retry
                break;
            }

            pending.append(buffer, buffer + n);

            // Extract complete '\n'-terminated lines.
            size_t pos;
            while ((pos = pending.find('\n')) != string::npos)
            {
                string line = pending.substr(0, pos);
                pending.erase(0, pos + 1);

                TrimCR(line);
                if (line.empty()) continue;

                // Expected: cusip,mid,topSpread
                stringstream ss(line);
                string cusip, midStr, spreadStr;
                if (!getline(ss, cusip, ',')) continue;
                if (!getline(ss, midStr, ',')) continue;
                if (!getline(ss, spreadStr)) continue;

                TrimCR(spreadStr);

                // Convert fractional -> decimal and forward into the service.
                double mid = FractionalToDecimal(midStr);
                double topSpread = FractionalToDecimal(spreadStr);

                service->BuildAndSendOrderBook(cusip, mid, topSpread);
            }
        }

        close(client_fd);
    }
}
