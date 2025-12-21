#ifndef BOND_RISK_HISTORICAL_LISTENER_HPP
#define BOND_RISK_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/riskservice.hpp"

#include "BondHistoricalDataService.hpp"
#include "RiskHistoricalConnector.hpp"

#include <string>

class BondRiskService; // forward decl (include BondRiskService.hpp in .cpp users if needed)

class BondRiskHistoricalListener : public ServiceListener<PV01<Bond>>
{
public:
    BondRiskHistoricalListener(
        BondHistoricalDataService<RiskLine>* hist,
        const BondRiskService* riskSvc
    )
        : histService(hist), riskService(riskSvc) {}

    void ProcessAdd(PV01<Bond>& pv) override { PersistAll(pv); }
    void ProcessUpdate(PV01<Bond>& pv) override { PersistAll(pv); }
    void ProcessRemove(PV01<Bond>&) override {}

private:
    void PersistAll(PV01<Bond>& pv)
    {
        // 1) SECURITY
        RiskLine sec;
        sec.type = RiskLineType::SECURITY;
        sec.name = pv.GetProduct().GetProductId();   // CUSIP
        sec.pv01 = pv.GetPV01();
        sec.qty = pv.GetQuantity();
        sec.pv01Usd = sec.pv01 * static_cast<double>(sec.qty);

        histService->PersistData(sec.name, sec);

        // 2) BUCKETS
        PersistBucket("FrontEnd");
        PersistBucket("Belly");
        PersistBucket("LongEnd");
    }

    void PersistBucket(const std::string& name)
    {
        // requires BondRiskService::GetBucketedRiskByName(name)
        const PV01<BucketedSector<Bond>>& b = riskService->GetBucketedRiskByName(name);

        RiskLine line;
        line.type = RiskLineType::BUCKET;
        line.name = name;

        // In your ComputeBucketRisk(): PV01 value = totalRisk = ¦²(pv01*qty), quantity=1
        line.pv01 = b.GetPV01();
        line.qty = b.GetQuantity();
        line.pv01Usd = b.GetPV01();

        histService->PersistData(name, line);
    }

private:
    BondHistoricalDataService<RiskLine>* histService;
    const BondRiskService* riskService;
};

#endif
