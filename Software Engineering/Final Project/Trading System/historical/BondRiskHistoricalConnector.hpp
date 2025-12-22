/**
 * RiskHistoricalConnector.hpp
 * Defines RiskLine (a simplified risk persistence record) and a connector that
 * appends RiskLine into risk.txt.
 *
 * Assignment requirement:
 * - Persist risk for each security (CUSIP)
 * - Persist bucket risk for FrontEnd, Belly, LongEnd
 *
 * Note:
 * - RiskLine is a "flat" structure written to file, independent from PV01<T>.
 * - Prices are NOT involved here; values are pv01 / pv01Usd.
 *
 * @author Hao Wang
 */

#ifndef BOND_RISK_HISTORICAL_CONNECTOR_HPP
#define BOND_RISK_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

 /**
  * RiskLineType
  * SECURITY: a single CUSIP risk line
  * BUCKET:   an aggregated sector risk line
  */
enum class RiskLineType { SECURITY, BUCKET };

/**
 * RiskLine
 * Flattened risk record persisted to file.
 *
 * Fields meaning:
 * - type: SECURITY or BUCKET
 * - name: CUSIP for SECURITY, or sector name for BUCKET
 * - pv01: SECURITY: per-unit PV01; BUCKET: total PV01USD (see pv01Usd)
 * - qty : SECURITY: position qty; BUCKET: usually 1 (implementation choice)
 * - pv01Usd: SECURITY: pv01*qty; BUCKET: total PV01USD
 */
struct RiskLine
{
    RiskLineType type;
    std::string  name;
    double       pv01;
    long         qty;
    double       pv01Usd;
};

/**
 * BondRiskHistoricalConnector
 * Appends RiskLine records into risk.txt.
 */
class BondRiskHistoricalConnector : public Connector< RiskLine >
{
public:
    /**
     * @param file Output file path (appended).
     */
    explicit BondRiskHistoricalConnector(const std::string& file = "risk.txt")
        : fileName(file)
    {
    }

    /**
     * Append one risk line into the output file.
     */
    void Publish(RiskLine& r) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[RiskHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        const char* tag = (r.type == RiskLineType::SECURITY) ? "SECURITY" : "BUCKET";

        fout << NowTimestampMS() << ","
            << tag << ","
            << r.name << ","
            << "PV01=" << r.pv01 << ","
            << "QTY=" << r.qty << ","
            << "PV01USD=" << r.pv01Usd
            << "\n";
    }

private:
    std::string fileName;
};

#endif
