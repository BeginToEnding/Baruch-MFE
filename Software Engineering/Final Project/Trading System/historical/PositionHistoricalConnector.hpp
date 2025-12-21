#ifndef BOND_POSITION_HISTORICAL_CONNECTOR_HPP
#define BOND_POSITION_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

class BondPositionHistoricalConnector : public Connector< Position<Bond> >
{
public:
    explicit BondPositionHistoricalConnector(const std::string& file = "positions.txt")
        : fileName(file) {}

    void Publish(Position<Bond>& pos) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[PosHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        const std::string cusip = pos.GetProduct().GetProductId();

        // Position::GetPosition takes string& (non-const), so create locals
        std::string b1 = "TRSY1", b2 = "TRSY2", b3 = "TRSY3";

        const long q1 = pos.GetPosition(b1);
        const long q2 = pos.GetPosition(b2);
        const long q3 = pos.GetPosition(b3);
        const long agg = pos.GetAggregatePosition();

        // One line per book + aggregate (explicitly required)
        fout << NowTimestampMS() << "," << cusip << ",BOOK=" << b1 << ",POS=" << q1 << "\n";
        fout << NowTimestampMS() << "," << cusip << ",BOOK=" << b2 << ",POS=" << q2 << "\n";
        fout << NowTimestampMS() << "," << cusip << ",BOOK=" << b3 << ",POS=" << q3 << "\n";
        fout << NowTimestampMS() << "," << cusip << ",BOOK=AGG,POS=" << agg << "\n";
    }

private:
    std::string fileName;
};

#endif
