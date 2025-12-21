#ifndef BOND_INQUIRY_HISTORICAL_CONNECTOR_HPP
#define BOND_INQUIRY_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/inquiryservice.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

class BondInquiryHistoricalConnector : public Connector< Inquiry<Bond> >
{
public:
    explicit BondInquiryHistoricalConnector(const std::string& file = "allinquiries.txt")
        : fileName(file) {}

    void Publish(Inquiry<Bond>& inq) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[InquiryHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        auto sideStr = [](Side s) { return (s == Side::BUY ? "BUY" : "SELL"); };
        auto stateStr = [](InquiryState st) {
            switch (st)
            {
            case InquiryState::RECEIVED: return "RECEIVED";
            case InquiryState::QUOTED:   return "QUOTED";
            case InquiryState::DONE:     return "DONE";
            case InquiryState::REJECTED: return "REJECTED";
            default:                     return "UNKNOWN";
            }
            };

        fout << NowTimestampMS() << ","
            << "INQID=" << inq.GetInquiryId() << ","
            << inq.GetProduct().GetProductId() << ","
            << "SIDE=" << sideStr(inq.GetSide()) << ","
            << "QTY=" << inq.GetQuantity() << ","
            << "PX=" << inq.GetPrice() << ","
            << "STATE=" << stateStr(inq.GetState())
            << "\n";
    }

private:
    std::string fileName;
};

#endif
