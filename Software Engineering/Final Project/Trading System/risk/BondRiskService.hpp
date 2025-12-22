/**
 * BondRiskService.hpp
 * Risk service implementation for US Treasury bonds (PV01 and bucketed PV01).
 *
 * This service is position-driven:
 *  - It receives Position<Bond> updates via a ServiceListener (Position -> Risk).
 *  - It computes single-name PV01 for each CUSIP.
 *  - It also computes bucketed PV01 for FrontEnd, Belly, LongEnd sectors.
 *
 * @author Hao Wang
 */

#ifndef BOND_RISK_SERVICE_HPP
#define BOND_RISK_SERVICE_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"
#include "../base/riskservice.hpp"
#include "../utils/ProductLookup.hpp"

#include <map>
#include <vector>
#include <string>

using namespace std;

/**
 * BondRiskService
 * Computes PV01 risk for each bond (single-name) and for bucketed sectors.
 */
class BondRiskService : public RiskService<Bond>
{
public:
    /**
     * Construct a BondRiskService.
     * Risk is computed from positions; no inbound connector is needed.
     */
    BondRiskService();

    /**
     * Get PV01 risk object by product identifier (CUSIP).
     *
     * @param key CUSIP
     * @return reference to PV01<Bond> stored in the service
     */
    virtual PV01<Bond>& GetData(string key) override;

    /**
     * Risk is position-driven in this project.
     * External connectors do not push PV01 directly, so this is a no-op.
     */
    virtual void OnMessage(PV01<Bond>& /*data*/) override {}

    /**
     * Register a listener for PV01 updates.
     *
     * @param listener listener to be notified on add/update
     */
    virtual void AddListener(ServiceListener<PV01<Bond>>* listener) override;

    /**
     * Get all PV01 listeners registered to this service.
     *
     * @return vector of listeners
     */
    virtual const vector<ServiceListener<PV01<Bond>>*>& GetListeners() const override;

    /**
     * Add/update a position in the Risk service.
     * This is called by the Position service via a ServiceListener chain.
     *
     * @param position updated Position<Bond> for a given CUSIP
     */
    void AddPosition(Position<Bond>& position);

    /**
     * Get bucketed risk by sector object.
     *
     * @param sector BucketedSector<Bond> object
     * @return PV01 for this bucket sector
     */
    const PV01<BucketedSector<Bond>>& GetBucketedRisk(const BucketedSector<Bond>& sector) const;

    /**
     * Get bucketed risk by sector name.
     *
     * @param sectorName "FrontEnd" / "Belly" / "LongEnd"
     * @return PV01 for this bucket sector
     */
    const PV01<BucketedSector<Bond>>& GetBucketedRiskByName(const string& sectorName) const;

private:
    /// Single-name PV01 keyed by CUSIP.
    map<string, PV01<Bond>> riskMap;

    /// Bucketed PV01 keyed by sector name.
    map<string, PV01<BucketedSector<Bond>>> bucketRiskMap;

    /// Registered listeners for PV01 updates.
    vector<ServiceListener<PV01<Bond>>*> listeners;

    /**
     * Return a realistic PV01 per 1bp move for a given CUSIP.
     * Values are hard-coded for the 7 on-the-run Treasuries.
     */
    double GetPV01Value(const string& cusip) const;

    /**
     * Recompute bucketed risks from the current single-name riskMap.
     * This should be called whenever riskMap is updated.
     */
    void ComputeBucketRisk();
};

#endif
