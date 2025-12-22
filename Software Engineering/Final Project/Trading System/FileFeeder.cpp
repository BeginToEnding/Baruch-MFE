/**
 * FileFeeder.cpp
 * A simple TCP feeder process:
 *   - Reads a text file line-by-line
 *   - Sends each line to a target <host:port> over TCP
 *   - Keeps ONE persistent TCP connection for high throughput (reconnect on failure)
 *
 * The trading system's inbound connectors (Pricing/MarketData/Trade/Inquiry) are TCP servers
 * listening on ports (e.g., 9001/9002/9003/9004). This feeder is the external publisher.
 *
 * Usage:
 *   feeder <file> <host> <port> [delay_ms]
 *
 * @author Hao Wang
 */

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

 /**
  * Send the entire buffer over a TCP socket.
  * TCP send() may send only part of the buffer, so we loop until all bytes are sent.
  *
  * @param sock  Connected TCP socket fd.
  * @param buf   Pointer to data buffer.
  * @param len   Number of bytes to send.
  * @return      True if all bytes were sent, false otherwise.
  */
static bool SendAll(int sock, const char* buf, size_t len)
{
    size_t sent = 0;
    while (sent < len)
    {
        int flags = 0;
#ifdef MSG_NOSIGNAL
        // Avoid SIGPIPE on Linux if the peer has closed unexpectedly.
        flags = MSG_NOSIGNAL;
#endif

        const ssize_t n = send(sock, buf + sent, len - sent, flags);
        if (n <= 0)
        {
            // n==0 or n<0 indicates failure/closed connection.
            return false;
        }

        sent += static_cast<size_t>(n);
    }
    return true;
}

/**
 * Create and connect a TCP socket to host:port.
 *
 * @param host  IPv4 address string (e.g., "127.0.0.1").
 * @param port  Target port number.
 * @return      Connected socket fd on success, or -1 on failure.
 */
static int ConnectOnce(const std::string& host, int port)
{
    // Create TCP socket.
    const int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) return -1;

    sockaddr_in serv;
    serv.sin_family = AF_INET;
    serv.sin_port = htons(static_cast<uint16_t>(port));

    // Convert "127.0.0.1" to network-byte-order address.
    if (inet_pton(AF_INET, host.c_str(), &serv.sin_addr) != 1)
    {
        close(sock);
        return -1;
    }

    // Connect to the trading system connector's listening port.
    if (connect(sock, reinterpret_cast<sockaddr*>(&serv), sizeof(serv)) < 0)
    {
        close(sock);
        return -1;
    }

    return sock;
}

/**
 * Program entry.
 * Reads <file> and publishes each line to <host:port>.
 *
 * We append '\n' to each line so the receiver can do line-based framing
 * (your connectors parse messages by searching for '\n').
 */
int main(int argc, char** argv)
{
    // Validate CLI args.
    if (argc < 4)
    {
        std::cerr << "Usage: feeder <file> <host> <port> [delay_ms]\n";
        return 1;
    }

    const std::string file = argv[1];
    const std::string host = argv[2];
    const int port = std::stoi(argv[3]);
    const int delayMs = (argc >= 5 ? std::stoi(argv[4]) : 0);

    // Open input file.
    std::ifstream fin(file.c_str());
    if (!fin.is_open())
    {
        std::cerr << "Cannot open file: " << file << "\n";
        return 1;
    }

    // One persistent connection is critical for large files (millions of lines).
    int sock = ConnectOnce(host, port);
    if (sock < 0)
    {
        std::cerr << "connect() failed on " << host << ":" << port << "\n";
        return 1;
    }

    std::string line;
    long long count = 0;

    while (std::getline(fin, line))
    {
        // Add newline delimiter so receiver can parse a complete message.
        line.push_back('\n');

        // Try send. If fails, reconnect once and retry the same line.
        if (!SendAll(sock, line.c_str(), line.size()))
        {
            // Close broken socket first.
            close(sock);

            // Backoff a bit to avoid tight reconnect loops.
            std::this_thread::sleep_for(std::chrono::milliseconds(50));

            sock = ConnectOnce(host, port);
            if (sock < 0)
            {
                std::cerr << "reconnect() failed on " << host << ":" << port << "\n";
                return 1;
            }

            if (!SendAll(sock, line.c_str(), line.size()))
            {
                std::cerr << "send() failed even after reconnect\n";
                close(sock);
                return 1;
            }
        }

        ++count;

        // Optional pacing for debugging / throttling.
        if (delayMs > 0)
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(delayMs));
        }

        // Progress logging (useful for 7,000,000+ lines).
        if (count % 100000 == 0)
        {
            std::cout << "Sent " << count << " lines to " << host << ":" << port << "\n";
        }
    }

    // Clean shutdown.
    close(sock);

    std::cout << "Done. Total sent: " << count << " lines to " << host << ":" << port << "\n";
    return 0;
}
