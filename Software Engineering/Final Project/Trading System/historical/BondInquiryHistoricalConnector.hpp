/**
 * BondInquiryHistoricalConnector.hpp
 * Connector used by BondHistoricalDataService<Inquiry<Bond>> to persist inquiries
 * into a file (default: allinquiries.txt).
 *
 * Output is newline-delimited CSV-like lines with:
 *   timestamp,INQID=...,CUSIP,SIDE=...,QTY=...,PX=...,STATE=...
 *
 * Prices are written in Treasury fractional notation per assignment requirement.
 *
 * @author Hao Wang
 */

#ifndef BOND_INQUIRY_HISTORICAL_CONNECTOR_HPP
#define BOND_INQUIRY_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/inquiryservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "../utils/TimeUtils.hpp"
#include "../utils/PriceUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

 /**
  * BondInquiryHistoricalConnector
  * Appends inquiry records into a text file.
  */
class BondInquiryHistoricalConnector : public Connector< Inquiry<Bond> >
{
public:
    /**
     * @param file Output file path (appended).
     */
    explicit BondInquiryHistoricalConnector(const std::string& file = "allinquiries.txt")
        : fileName(file)
    {
    }

    /**
     * Append one inquiry snapshot to file.
     * This method is called by BondHistoricalDataService::PersistData().
     */
    void Publish(Inquiry<Bond>& inq) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[InquiryHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        // Convert enums to readable tags for logging.
        const char* side =
            (inq.GetSide() == Side::BUY) ? "BUY" : "SELL";

        const char* state = "UNKNOWN";
        switch (inq.GetState())
        {
        case InquiryState::RECEIVED: state = "RECEIVED"; break;
        case InquiryState::QUOTED:   state = "QUOTED";   break;
        case InquiryState::DONE:     state = "DONE";     break;
        case InquiryState::REJECTED: state = "REJECTED"; break;
        default:                     state = "UNKNOWN";  break;
        }

        // Price is stored internally as decimal; convert to fractional on output.
        fout << NowTimestampMS() << ","
            << "INQID=" << inq.GetInquiryId() << ","
            << inq.GetProduct().GetProductId() << ","
            << "SIDE=" << side << ","
            << "QTY=" << inq.GetQuantity() << ","
            << "PX=" << DecimalToFractional(inq.GetPrice()) << ","
            << "STATE=" << state
            << "\n";
    }

private:
    std::string fileName;
};

#endif
