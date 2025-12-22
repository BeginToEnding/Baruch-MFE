/**
 * BondInquiryConnector.cpp
 * Implements the inquiry socket connector.
 *
 * - Start(): listens on port and parses incoming inquiry lines.
 * - Publish(): sends QUOTED then DONE back into same port (loopback).
 *
 * Prices on the wire are fractional strings, converted to decimal internally.
 *
 * @author Hao Wang
 */

#include "BondInquiryConnector.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"

#include <sstream>
#include <iostream>
#include <string>
#include <cerrno>
#include <cstring>

 // POSIX sockets (WSL/Linux)
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>

using namespace std;

/**
 * Trim trailing '\r' from a line (Windows CRLF support).
 */
static inline void TrimCR(string& s)
{
    if (!s.empty() && s.back() == '\r') s.pop_back();
}

/**
 * Parse inquiry state string into enum.
 */
static inline InquiryState ParseState(const string& s)
{
    if (s == "RECEIVED") return InquiryState::RECEIVED;
    if (s == "QUOTED")   return InquiryState::QUOTED;
    if (s == "DONE")     return InquiryState::DONE;
    if (s == "REJECTED") return InquiryState::REJECTED;
    return InquiryState::RECEIVED;
}

BondInquiryConnector::BondInquiryConnector(BondInquiryService* s, int p)
    : service(s), port(p)
{
}

void BondInquiryConnector::Start()
{
    // Create server socket.
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0)
    {
        cerr << "[InquiryConnector] socket() failed: " << strerror(errno) << "\n";
        return;
    }

    // Allow quick restart on same port.
    int opt = 1;
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0)
    {
        cerr << "[InquiryConnector] setsockopt() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    // Bind and listen.
    if (bind(server_fd, (sockaddr*)&address, sizeof(address)) < 0)
    {
        cerr << "[InquiryConnector] bind() failed on port " << port
            << ": " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    if (listen(server_fd, 128) < 0)
    {
        cerr << "[InquiryConnector] listen() failed: " << strerror(errno) << "\n";
        close(server_fd);
        return;
    }

    cout << "[InquiryConnector] Listening on port " << port << endl;

    // Accept loop: each client may send multiple '\n' delimited lines.
    while (true)
    {
        socklen_t addrlen = sizeof(address);
        int client_fd = accept(server_fd, (sockaddr*)&address, &addrlen);
        if (client_fd < 0)
        {
            cerr << "[InquiryConnector] accept() failed: " << strerror(errno) << "\n";
            continue;
        }

        string pending;
        char buffer[4096];

        // Read until client closes.
        while (true)
        {
            ssize_t n = read(client_fd, buffer, sizeof(buffer));
            if (n == 0) break;         // peer closed
            if (n < 0)
            {
                if (errno == EINTR) continue; // retry on interrupt
                break;
            }

            // Append received bytes, then parse complete lines.
            pending.append(buffer, buffer + n);

            size_t pos;
            while ((pos = pending.find('\n')) != string::npos)
            {
                string line = pending.substr(0, pos);
                pending.erase(0, pos + 1);

                TrimCR(line);
                if (line.empty()) continue;

                // format from file/feeder:
                //   id,cusip,side,qty,pxFrac
                // format from Publish loopback:
                //   id,cusip,side,qty,pxFrac,STATE
                stringstream ss(line);

                string id, cusip, sideStr, qtyStr, pxStr, stateStr;
                if (!getline(ss, id, ',')) continue;
                if (!getline(ss, cusip, ',')) continue;
                if (!getline(ss, sideStr, ',')) continue;
                if (!getline(ss, qtyStr, ',')) continue;
                if (!getline(ss, pxStr, ',')) continue; // reads until comma or end
                getline(ss, stateStr);                  // optional (may be empty)

                TrimCR(pxStr);
                TrimCR(stateStr);

                // Lookup product by CUSIP.
                const Bond& product = ProductLookup::GetBond(cusip);

                // Parse side/qty/price.
                Side side = (sideStr == "BUY") ? Side::BUY : Side::SELL;
                long qty = stol(qtyStr);

                // Fractional on the wire -> decimal internal
                double price = FractionalToDecimal(pxStr);

                InquiryState st = stateStr.empty()
                    ? InquiryState::RECEIVED
                    : ParseState(stateStr);

                Inquiry<Bond> inq(id, product, side, qty, price, st);

                // Push into the service.
                service->OnMessage(inq);
            }
        }

        close(client_fd);
    }
}

void BondInquiryConnector::Publish(Inquiry<Bond>& data)
{
    // Send QUOTED then DONE back into the same listening port.
    // Using two short-lived connections is acceptable for this assignment scale.

    /**
     * Send one state transition back to the local listener.
     */
    auto sendOne = [&](const string& state)
        {
            int sock = socket(AF_INET, SOCK_STREAM, 0);
            if (sock < 0) return;

            sockaddr_in serv{};
            serv.sin_family = AF_INET;
            serv.sin_port = htons(port);
            serv.sin_addr.s_addr = inet_addr("127.0.0.1");

            if (connect(sock, (sockaddr*)&serv, sizeof(serv)) < 0)
            {
                close(sock);
                return;
            }

            // Keep price in fractional format on the wire.
            stringstream ss;
            ss << data.GetInquiryId() << ","
                << data.GetProduct().GetProductId() << ","
                << (data.GetSide() == Side::BUY ? "BUY" : "SELL") << ","
                << data.GetQuantity() << ","
                << DecimalToFractional(data.GetPrice()) << ","
                << state
                << "\n";

            const string msg = ss.str();

            // Best-effort send; errors are ignored for simplicity.
            send(sock, msg.c_str(), msg.size(), 0);
            close(sock);
        };

    // Per spec: QUOTED then immediately DONE.
    sendOne("QUOTED");
    sendOne("DONE");
}
