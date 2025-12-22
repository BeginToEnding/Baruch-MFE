/**
 * BondPricingConnector.cpp
 * Implementation of the inbound pricing connector.
 *
 * @author Hao Wang
 */

#include "BondPricingConnector.hpp"
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

BondPricingConnector::BondPricingConnector(BondPricingService* s, int p)
    : service(s), port(p) {}

/**
 * Remove trailing '\r' so CRLF lines are accepted.
 */
static inline void TrimCR(string& s)
{
    if (!s.empty() && s.back() == '\r') s.pop_back();
}

void BondPricingConnector::Start()
{
    // Create a TCP listening socket.
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
    {
        cerr << "[PricingConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    // Allow quick restart on same port (avoid TIME_WAIT issues).
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        cerr << "[PricingConnector] setsockopt(SO_REUSEADDR) failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (sockaddr*)&address, sizeof(address)) < 0)
    {
        cerr << "[PricingConnector] bind() failed on port " << port << ": " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    if (listen(server_fd, 128) < 0)
    {
        cerr << "[PricingConnector] listen() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    cout << "[PricingConnector] Listening on port " << port << endl;

    // Accept connections forever. One connection may stream many lines.
    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (sockaddr*)&address, &addrlen);
        if (client_fd < 0)
        {
            cerr << "[PricingConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        // pending accumulates partial TCP fragments until we have full lines '\n'.
        string pending;
        char buffer[4096];

        while (true)
        {
            // read() may return partial message, multiple messages, or 0 (peer closed).
            ssize_t n = read(client_fd, buffer, sizeof(buffer));
            if (n == 0) break;                // client closed
            if (n < 0)
            {
                if (errno == EINTR) continue; // interrupted, retry
                cerr << "[PricingConnector] read() failed: " << strerror(errno) << "\n";
                break;
            }

            pending.append(buffer, buffer + n);

            // Process all complete lines currently in pending.
            size_t nl;
            while ((nl = pending.find('\n')) != string::npos)
            {
                string line = pending.substr(0, nl);
                pending.erase(0, nl + 1);

                TrimCR(line);
                if (line.empty()) continue;

                // Expected: cusip,mid,spread
                stringstream ss(line);
                string cusip, midStr, sprStr;
                if (!getline(ss, cusip, ',')) continue;
                if (!getline(ss, midStr, ',')) continue;
                if (!getline(ss, sprStr)) continue;

                TrimCR(sprStr);

                try
                {
                    // Convert fractional -> decimal for internal computation.
                    double mid = FractionalToDecimal(midStr);
                    double spread = FractionalToDecimal(sprStr);

                    // Push into service (service will create Price<Bond> and notify listeners).
                    service->UpdatePrice(cusip, mid, spread);
                }
                catch (const exception&)
                {
                    // Bad line; skip silently (or add logging if debugging).
                }
            }
        }

        close(client_fd);
    }

    // close(server_fd); // unreachable
}
