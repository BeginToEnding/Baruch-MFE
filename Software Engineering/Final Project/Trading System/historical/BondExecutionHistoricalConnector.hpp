/**
 * BondExecutionHistoricalConnector.hpp
 * Connector used by BondHistoricalDataService<ExecutionOrder<Bond>> to persist executions
 * into a file (default: executions.txt).
 *
 * Output format:
 *   timestamp,cusip,ORDERID=...,SIDE=...,PX=...,QTY=...
 *
 * Prices are written in Treasury fractional notation per assignment requirement.
 *
 * @author Hao Wang
 */

#ifndef BOND_EXECUTION_HISTORICAL_CONNECTOR_HPP
#define BOND_EXECUTION_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/executionservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "../utils/TimeUtils.hpp"
#include "../utils/PriceUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

 /**
  * BondExecutionHistoricalConnector
  * Appends execution snapshots into a text file.
  */
class BondExecutionHistoricalConnector : public Connector< ExecutionOrder<Bond> >
{
public:
    /**
     * @param file Output file path (appended).
     */
    explicit BondExecutionHistoricalConnector(const std::string& file = "executions.txt")
        : fileName(file)
    {
    }

    /**
     * Append one execution snapshot into the output file.
     */
    void Publish(ExecutionOrder<Bond>& o) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[ExecHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        // PricingSide::BID means we are buying (we hit the offer in the market).
        const char* side =
            (o.GetSide() == PricingSide::BID) ? "BUY" : "SELL";

        fout << NowTimestampMS() << ","
            << o.GetProduct().GetProductId() << ","
            << "ORDERID=" << o.GetOrderId() << ","
            << "SIDE=" << side << ","
            << "PX=" << DecimalToFractional(o.GetPrice()) << ","
            << "QTY=" << o.GetVisibleQuantity()
            << "\n";
    }

private:
    std::string fileName;
};

#endif
