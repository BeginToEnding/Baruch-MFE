/**
 * BondTradeBookingConnector.cpp
 * Implementation of the inbound trade booking connector.
 *
 * @author Hao Wang
 */

#include "BondTradeBookingConnector.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../utils//Books.hpp"

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

BondTradeBookingConnector::BondTradeBookingConnector(BondTradeBookingService* service_, int port_)
    : service(service_), port(port_) {}

/**
 * Remove trailing '\r' so CRLF lines are accepted.
 */
static inline void TrimCR(string& s)
{
    if (!s.empty() && s.back() == '\r') s.pop_back();
}

void BondTradeBookingConnector::Start()
{
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
    {
        cerr << "[TradeBookingConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        cerr << "[TradeBookingConnector] setsockopt() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (sockaddr*)&address, sizeof(address)) < 0)
    {
        cerr << "[TradeBookingConnector] bind() failed on port " << port
            << ": " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    if (listen(server_fd, 128) < 0)
    {
        cerr << "[TradeBookingConnector] listen() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    cout << "[TradeBookingConnector] Listening on port " << port << endl;

    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (sockaddr*)&address, &addrlen);
        if (client_fd < 0)
        {
            cerr << "[TradeBookingConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        // One client may stream many trade lines.
        string pending;
        char buffer[4096];

        while (true)
        {
            ssize_t n = read(client_fd, buffer, sizeof(buffer));
            if (n == 0) break; // peer closed
            if (n < 0)
            {
                if (errno == EINTR) continue;
                break;
            }

            pending.append(buffer, buffer + n);

            // Parse complete newline-delimited records.
            size_t pos;
            while ((pos = pending.find('\n')) != string::npos)
            {
                string line = pending.substr(0, pos);
                pending.erase(0, pos + 1);

                TrimCR(line);
                if (line.empty()) continue;

                // Expected: cusip,side,qty,px,tradeId
                stringstream ss(line);
                string cusip, sideStr, qtyStr, pxStr, tradeId;
                if (!getline(ss, cusip, ',')) continue;
                if (!getline(ss, sideStr, ',')) continue;
                if (!getline(ss, qtyStr, ',')) continue;
                if (!getline(ss, pxStr, ',')) continue;
                if (!getline(ss, tradeId)) continue;

                TrimCR(tradeId);

                // Convert CUSIP -> product object (Treasury derives from Bond).
                const Bond& product = ProductLookup::GetBond(cusip);

                // Normalize side tokens.
                Side side = (sideStr == "BUY" || sideStr == "BID") ? BUY : SELL;

                long qty = stol(qtyStr);

                // Convert price fractional -> decimal for internal storage.
                double px = FractionalToDecimal(pxStr);

                // Project spec: cycle through books TRSY1, TRSY2, TRSY3.
                static int bookIdx = 0;
                const std::string book = NextBook(bookIdx);

                Trade<Bond> trade(product, tradeId, px, book, qty, side);

                // Base contract: BookTrade() is the official entry point.
                if (service) service->BookTrade(trade);
            }
        }

        ::close(client_fd);
    }

    // ::close(server_fd); // unreachable in this design
}


