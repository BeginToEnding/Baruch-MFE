#include "BondPricingConnector.hpp"
#include <sstream>
#include <iostream>
#include <string>
#include <vector>
#include <cerrno>
#include <cstring>

void BondPricingConnector::Start()
{
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        std::cerr << "[PricingConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        std::cerr << "[PricingConnector] setsockopt() failed: " << strerror(errno) << "\n";
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    if (bind(server_fd, (struct sockaddr*)&address, sizeof(address)) < 0) {
        std::cerr << "[PricingConnector] bind() failed on port " << port
            << ": " << strerror(errno) << "\n";
        return;
    }

    if (listen(server_fd, 128) < 0) {
        std::cerr << "[PricingConnector] listen() failed: " << strerror(errno) << "\n";
        return;
    }

    std::cout << "[PricingConnector] Listening on port " << port << std::endl;

    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (struct sockaddr*)&address, &addrlen);
        if (client_fd < 0) {
            std::cerr << "[PricingConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        std::string pending;
        char buffer[4096];

        while (true)
        {
            int n = read(client_fd, buffer, sizeof(buffer));
            if (n <= 0) break; // 0=closed, <0=error

            pending.append(buffer, buffer + n);

            // process full lines
            size_t pos;
            while ((pos = pending.find('\n')) != std::string::npos)
            {
                std::string line = pending.substr(0, pos);
                pending.erase(0, pos + 1);

                if (!line.empty() && line.back() == '\r') line.pop_back();
                if (line.empty()) continue;

                std::stringstream ss(line);
                std::string cusip, fracMid, fracSpread;

                if (!std::getline(ss, cusip, ',')) continue;
                if (!std::getline(ss, fracMid, ',')) continue;
                if (!std::getline(ss, fracSpread)) continue;

                if (!fracSpread.empty() && fracSpread.back() == '\r') fracSpread.pop_back();

                double mid = FractionalToDecimal(fracMid);
                double spread = FractionalToDecimal(fracSpread);

                service->UpdatePrice(cusip, mid, spread);
            }
        }

        close(client_fd);
    }
}
