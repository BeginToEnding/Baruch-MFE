// ====================== BondMarketDataConnector.cpp ======================
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

BondMarketDataConnector::BondMarketDataConnector(BondMarketDataService* s, int p)
    : service(s), port(p) {}

static inline void TrimCR(std::string& s)
{
    if (!s.empty() && s.back() == '\r') s.pop_back();
}

void BondMarketDataConnector::Start()
{
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
    {
        std::cerr << "[MarketDataConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        std::cerr << "[MarketDataConnector] setsockopt() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) < 0)
    {
        std::cerr << "[MarketDataConnector] bind() failed on port " << port
            << ": " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    if (listen(server_fd, 128) < 0)
    {
        std::cerr << "[MarketDataConnector] listen() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    std::cout << "[MarketDataConnector] Listening on port " << port << std::endl;

    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (struct sockaddr*)&address, &addrlen);
        if (client_fd < 0)
        {
            std::cerr << "[MarketDataConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        // Support long-lived connections: one client can stream many lines.
        std::string pending;
        char buffer[4096];

        while (true)
        {
            int n = read(client_fd, buffer, sizeof(buffer));
            if (n <= 0) break; // 0=client closed, <0=error

            pending.append(buffer, buffer + n);

            // Process complete lines (handles TCP framing: split/merged packets)
            size_t pos;
            while ((pos = pending.find('\n')) != std::string::npos)
            {
                std::string line = pending.substr(0, pos);
                pending.erase(0, pos + 1);

                TrimCR(line);
                if (line.empty()) continue;

                // Expected format: cusip,mid,topSpread
                // Example: 91282CGW5,99.00390625,0.0078125
                std::stringstream ss(line);

                std::string cusip, midStr, spreadStr;
                if (!std::getline(ss, cusip, ',')) continue;
                if (!std::getline(ss, midStr, ',')) continue;
                if (!std::getline(ss, spreadStr)) continue; // last field to end of line

                TrimCR(spreadStr);

                // Choose ONE format and keep consistent between feeder and connector.
                // Option A (recommended): decimal
                double mid = FractionalToDecimal(midStr);
                double topSpread = FractionalToDecimal(spreadStr);

                // Option B: fractional (uncomment if your marketdata.txt uses fractional strings)
                // double mid = FractionalToDecimal(midStr);
                // double topSpread = FractionalToDecimal(spreadStr);

                service->BuildAndSendOrderBook(cusip, mid, topSpread);
            }
        }

        close(client_fd);
    }

    // close(server_fd); // unreachable in typical daemon loop
}
