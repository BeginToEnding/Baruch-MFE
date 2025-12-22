/**
 * BondRiskHistoricalListener.hpp
 * Listener that subscribes to BondRiskService (PV01<Bond> stream) and persists:
 * - security-level risk lines (one per CUSIP)
 * - bucket-level risk lines (FrontEnd, Belly, LongEnd)
 *
 * Implementation notes:
 * - This listener depends on BondRiskService to provide bucketed PV01 via
 *   GetBucketedRiskByName().
 * - It converts PV01<Bond> and PV01<BucketedSector<Bond>> into RiskLine objects
 *   and persists them using BondHistoricalDataService<RiskLine>.
 *
 * @author Hao Wang
 */

#ifndef BOND_RISK_HISTORICAL_LISTENER_HPP
#define BOND_RISK_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/riskservice.hpp"
#include "../products/TreasuryProducts.hpp"

#include "BondHistoricalDataService.hpp"
#include "BondRiskHistoricalConnector.hpp"
#include "../risk/BondRiskService.hpp"

#include <string>

 // Forward declaration to avoid including the whole BondRiskService header here.
 // The translation unit that instantiates this listener should include BondRiskService.hpp.
class BondRiskService;

/**
 * BondRiskHistoricalListener
 * Persists both single-name and bucket risk lines into the historical service.
 */
class BondRiskHistoricalListener : public ServiceListener< PV01<Bond> >
{
public:
    /**
     * @param hist     Historical service for RiskLine output.
     * @param riskSvc  BondRiskService used to query bucketed risk snapshots.
     */
    BondRiskHistoricalListener(
        BondHistoricalDataService<RiskLine>* hist,
        const BondRiskService* riskSvc
    )
        : histService(hist),
        riskService(riskSvc)
    {
    }

    void ProcessAdd(PV01<Bond>& pv) override { PersistAll(pv); }
    void ProcessUpdate(PV01<Bond>& pv) override { PersistAll(pv); }
    void ProcessRemove(PV01<Bond>&) override {}

private:
    /**
     * Persist security line + all bucket lines for every PV01 update.
     * This matches the assignment's requirement to keep buckets updated as positions move.
     */
    void PersistAll(PV01<Bond>& pv)
    {
        // -------------------------
        // 1) SECURITY risk line
        // -------------------------
        RiskLine sec;
        sec.type = RiskLineType::SECURITY;
        sec.name = pv.GetProduct().GetProductId(); // CUSIP
        sec.pv01 = pv.GetPV01();
        sec.qty = pv.GetQuantity();
        sec.pv01Usd = sec.pv01 * static_cast<double>(sec.qty);

        // Persist keyed by CUSIP.
        histService->PersistData(sec.name, sec);

        // -------------------------
        // 2) BUCKET risk lines
        // -------------------------
        PersistBucket("FrontEnd");
        PersistBucket("Belly");
        PersistBucket("LongEnd");
    }

    /**
     * Persist one bucket risk line by name.
     */
    void PersistBucket(const std::string& name)
    {
        // Requires BondRiskService::GetBucketedRiskByName(name).
        const PV01< BucketedSector<Bond> >& b = riskService->GetBucketedRiskByName(name);

        RiskLine line;
        line.type = RiskLineType::BUCKET;
        line.name = name;

        // In your ComputeBucketRisk(), PV01 value is totalRisk = ¦²(pv01*qty), quantity=1.
        // We keep pv01Usd = totalRisk for easy reading in the output file.
        line.pv01 = b.GetPV01();
        line.qty = b.GetQuantity();
        line.pv01Usd = b.GetPV01();

        // Persist keyed by bucket name.
        histService->PersistData(name, line);
    }

private:
    BondHistoricalDataService<RiskLine>* histService;
    const BondRiskService* riskService;
};

#endif
