#ifndef BOND_RISK_HISTORICAL_CONNECTOR_HPP
#define BOND_RISK_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

enum class RiskLineType { SECURITY, BUCKET };

struct RiskLine
{
    RiskLineType type;     // SECURITY or BUCKET
    std::string  name;     // SECURITY: CUSIP, BUCKET: FrontEnd/Belly/LongEnd
    double       pv01;     // SECURITY: per-unit PV01, BUCKET: total PV01USD (see pv01Usd)
    long         qty;      // SECURITY: position qty, BUCKET: 1
    double       pv01Usd;  // SECURITY: pv01*qty, BUCKET: total PV01USD
};

class BondRiskHistoricalConnector : public Connector<RiskLine>
{
public:
    explicit BondRiskHistoricalConnector(const std::string& file = "risk.txt")
        : fileName(file) {}

    void Publish(RiskLine& r) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[RiskHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        const char* tag = (r.type == RiskLineType::SECURITY ? "SECURITY" : "BUCKET");

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
