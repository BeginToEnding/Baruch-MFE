#ifndef BOND_EXECUTION_HISTORICAL_CONNECTOR_HPP
#define BOND_EXECUTION_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/executionservice.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

class BondExecutionHistoricalConnector : public Connector< ExecutionOrder<Bond> >
{
public:
    explicit BondExecutionHistoricalConnector(const std::string& file = "executions.txt")
        : fileName(file) {}

    void Publish(ExecutionOrder<Bond>& o) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[ExecHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        auto sideStr = [](PricingSide s) { return (s == PricingSide::BID ? "BUY" : "SELL"); };

        fout << NowTimestampMS() << ","
            << o.GetProduct().GetProductId() << ","
            << "ORDERID=" << o.GetOrderId() << ","
            << "SIDE=" << sideStr(o.GetSide()) << ","
            << "PX=" << o.GetPrice() << ","
            << "QTY=" << o.GetVisibleQuantity()
            << "\n";
    }

private:
    std::string fileName;
};

#endif
