// ====================== BondInquiryConnector.cpp ======================
#include "BondInquiryConnector.hpp"
#include <iostream>

BondInquiryConnector::BondInquiryConnector(BondInquiryService* s, int p)
    : service(s), port(p)
{
}

void BondInquiryConnector::Start()
{
    int server_fd, new_socket;
    struct sockaddr_in address {};
    int opt = 1;
    socklen_t addrlen = sizeof(address);
    char buffer[256];

    server_fd = socket(AF_INET, SOCK_STREAM, 0);
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT,
        &opt, sizeof(opt));

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port);

    bind(server_fd, (struct sockaddr*)&address, sizeof(address));
    listen(server_fd, 3);

    std::cout << "[InquiryConnector] Listening on port " << port << std::endl;

    while (true)
    {
        new_socket = accept(server_fd, (struct sockaddr*)&address, &addrlen);

        int n = read(new_socket, buffer, 255);
        buffer[n] = '\0';
        close(new_socket);

        std::string line(buffer);
        std::stringstream ss(line);

        string id, cusip, sideStr, qtyStr, pxStr;
        getline(ss, id, ',');
        getline(ss, cusip, ',');
        getline(ss, sideStr, ',');
        getline(ss, qtyStr, ',');
        getline(ss, pxStr, ',');

        const TreasuryProduct& tp = LookupCUSIP(cusip);

        Side side = (sideStr == "BUY" ? Side::BUY : Side::SELL);
        long qty = stol(qtyStr);
        double price = stod(pxStr);

        Inquiry<Bond> inq(
            id, tp.GetBond(), side, qty, price,
            InquiryState::RECEIVED
        );

        service->OnMessage(inq);
    }
}

//
// Called when service.SendQuote() or RejectInquiry() is triggered
//
void BondInquiryConnector::Publish(Inquiry<Bond>& data)
{
    // Step 1: send quoted state back
    {
        int sock = socket(AF_INET, SOCK_STREAM, 0);

        struct sockaddr_in serv {};
        serv.sin_family = AF_INET;
        serv.sin_port = htons(port);
        serv.sin_addr.s_addr = inet_addr("127.0.0.1");

        connect(sock, (struct sockaddr*)&serv, sizeof(serv));

        std::stringstream ss;
        ss << data.GetInquiryId() << ","
            << data.GetProduct().GetProductId() << ","
            << (data.GetSide() == Side::BUY ? "BUY" : "SELL") << ","
            << data.GetQuantity() << ","
            << data.GetPrice() << ","
            << "QUOTED";

        string msg = ss.str();
        send(sock, msg.c_str(), msg.size(), 0);
        close(sock);
    }

    // Step 2: immediately send DONE state
    {
        int sock = socket(AF_INET, SOCK_STREAM, 0);

        struct sockaddr_in serv {};
        serv.sin_family = AF_INET;
        serv.sin_port = htons(port);
        serv.sin_addr.s_addr = inet_addr("127.0.0.1");

        connect(sock, (struct sockaddr*)&serv, sizeof(serv));

        std::stringstream ss;
        ss << data.GetInquiryId() << ","
            << data.GetProduct().GetProductId() << ","
            << (data.GetSide() == Side::BUY ? "BUY" : "SELL") << ","
            << data.GetQuantity() << ","
            << data.GetPrice() << ","
            << "DONE";

        string msg = ss.str();
        send(sock, msg.c_str(), msg.size(), 0);
        close(sock);
    }
}
