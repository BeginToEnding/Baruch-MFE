/**
 * BondPositionHistoricalConnector.hpp
 * Connector used by BondHistoricalDataService<Position<Bond>> to persist positions
 * into a file (default: positions.txt).
 *
 * Assignment requirement:
 * - Persist each position for each book (TRSY1/TRSY2/TRSY3)
 * - Persist the aggregate position as BOOK=AGG
 *
 * Timestamp:
 * - We want all four lines to share the same timestamp, so we capture it once.
 *
 * @author Hao Wang
 */

#ifndef BOND_POSITION_HISTORICAL_CONNECTOR_HPP
#define BOND_POSITION_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

 /**
  * BondPositionHistoricalConnector
  * Appends position snapshots (per book + aggregate) into positions.txt.
  */
class BondPositionHistoricalConnector : public Connector< Position<Bond> >
{
public:
    /**
     * @param file Output file path (appended).
     */
    explicit BondPositionHistoricalConnector(const std::string& file = "positions.txt")
        : fileName(file)
    {
    }

    /**
     * Append one position snapshot into file.
     * This writes 4 lines: TRSY1, TRSY2, TRSY3, AGG.
     */
    void Publish(Position<Bond>& pos) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[PosHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        const std::string cusip = pos.GetProduct().GetProductId();

        // Position::GetPosition takes string& (non-const), so create local book strings.
        std::string b1 = "TRSY1";
        std::string b2 = "TRSY2";
        std::string b3 = "TRSY3";

        const long q1 = pos.GetPosition(b1);
        const long q2 = pos.GetPosition(b2);
        const long q3 = pos.GetPosition(b3);
        const long agg = pos.GetAggregatePosition();

        // Use one consistent timestamp for the four lines (prevents drift).
        const string ts = NowTimestampMS();

        // One line per book + aggregate (explicitly required).
        fout << ts << "," << cusip << ",BOOK=" << b1 << ",POS=" << q1 << "\n";
        fout << ts << "," << cusip << ",BOOK=" << b2 << ",POS=" << q2 << "\n";
        fout << ts << "," << cusip << ",BOOK=" << b3 << ",POS=" << q3 << "\n";
        fout << ts << "," << cusip << ",BOOK=AGG,POS=" << agg << "\n";
    }

private:
    std::string fileName;
};

#endif
