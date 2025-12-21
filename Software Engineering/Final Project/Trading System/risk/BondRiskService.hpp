// ====================== BondRiskService.hpp ======================
#ifndef BOND_RISK_SERVICE_HPP
#define BOND_RISK_SERVICE_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"
#include "../base/riskservice.hpp"
#include "../utils/ProductLookup.hpp"
#include <map>
#include <vector>

class BondRiskService : public RiskService<Bond>
{
public:
    BondRiskService();

    // Service interface
    PV01<Bond>& GetData(string key) override;

    // Risk is position-driven in this project; no external connector pushes PV01 directly.
    void OnMessage(PV01<Bond>& /*data*/) override {}

    void AddListener(ServiceListener<PV01<Bond>>* listener) override;
    const vector<ServiceListener<PV01<Bond>>*>& GetListeners() const override;

    // Called by PositionService (via a listener)
    void AddPosition(Position<Bond>& position);

    // Bucketed risk access
    const PV01<BucketedSector<Bond>>& GetBucketedRisk(const BucketedSector<Bond>& sector) const;

    const PV01<BucketedSector<Bond>>& GetBucketedRiskByName(const string& sectorName) const;

private:
    // Single-name PV01 for each product
    map<string, PV01<Bond>> riskMap;

    // Bucketed PV01 by sector name
    map<string, PV01<BucketedSector<Bond>>> bucketRiskMap;

    vector<ServiceListener<PV01<Bond>>*> listeners;

    double GetPV01Value(const string& cusip) const;

    // Compute bucketed risk from current single-name riskMap
    void ComputeBucketRisk();
};

#endif
