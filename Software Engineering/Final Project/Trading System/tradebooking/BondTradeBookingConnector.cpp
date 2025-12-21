// ====================== BondTradeBookingConnector.cpp ======================
#include "BondTradeBookingConnector.hpp"
#include <sstream>
#include <iostream>

BondTradeBookingConnector::BondTradeBookingConnector(BondTradeBookingService* service_, int port_)
    : service(service_), port(port_) {}

static inline void TrimCR(std::string& s)
{
    if (!s.empty() && s.back() == '\r') s.pop_back();
}

void BondTradeBookingConnector::Start()
{
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
    {
        std::cerr << "[TradeBookingConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        std::cerr << "[TradeBookingConnector] setsockopt() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) < 0)
    {
        std::cerr << "[TradeBookingConnector] bind() failed on port " << port
            << ": " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    if (listen(server_fd, 128) < 0)
    {
        std::cerr << "[TradeBookingConnector] listen() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    std::cout << "[TradeBookingConnector] Listening on port " << port << std::endl;

    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (struct sockaddr*)&address, &addrlen);
        if (client_fd < 0)
        {
            std::cerr << "[TradeBookingConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        std::string pending;
        char buffer[4096];

        while (true)
        {
            int n = read(client_fd, buffer, sizeof(buffer));
            if (n <= 0) break; // 0=client closed, <0=error

            pending.append(buffer, buffer + n);

            size_t pos;
            while ((pos = pending.find('\n')) != std::string::npos)
            {
                std::string line = pending.substr(0, pos);
                pending.erase(0, pos + 1);

                TrimCR(line);
                if (line.empty()) continue;

                // format：cusip,side,qty,px,tradeId
                // ex：91282CGW5,BUY,1000000,99.125,TRD0001
                std::stringstream ss(line);

                std::string cusip, sideStr, qtyStr, pxStr, tradeId;
                if (!std::getline(ss, cusip, ',')) continue;
                if (!std::getline(ss, sideStr, ',')) continue;
                if (!std::getline(ss, qtyStr, ',')) continue;
                if (!std::getline(ss, pxStr, ',')) continue;
                if (!std::getline(ss, tradeId)) continue;

                TrimCR(tradeId);

                const Treasury& product = ProductLookup::GetBond(cusip);

                Side side;
                if (sideStr == "BUY" || sideStr == "BID") side = BUY;
                else side = SELL;

                long qty = std::stol(qtyStr);
                
                double px = FractionalToDecimal(pxStr);

                static int bookIdx = 0;
                static const char* books[] = { "TRSY1","TRSY2","TRSY3" };
                std::string book = books[bookIdx++ % 3];
                Trade<Bond> trade(product, tradeId, px, book, qty, side);

            
                service->BookTrade(trade);
            }
        }

        close(client_fd);
    }

    // close(server_fd);
}
