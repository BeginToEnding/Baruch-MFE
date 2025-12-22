/**
 * BondRiskService.cpp
 * Implementation of BondRiskService.
 *
 * @author Hao Wang
 */

#include "BondRiskService.hpp"

BondRiskService::BondRiskService() = default;

PV01<Bond>& BondRiskService::GetData(string key)
{
    // at() throws if the key does not exist; this is acceptable if caller ensures existence.
    return riskMap.at(key);
}

void BondRiskService::AddListener(ServiceListener<PV01<Bond>>* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener<PV01<Bond>>*>& BondRiskService::GetListeners() const
{
    return listeners;
}

double BondRiskService::GetPV01Value(const string& cusip) const
{
    // Realistic PV01 values for the 7 on-the-run Treasuries.
    static map<string, double> pv01 = {
        {"91282CGW5", 0.018}, // 2Y
        {"91282CGZ8", 0.030}, // 3Y
        {"91282CHA2", 0.045}, // 5Y
        {"91282CHD6", 0.060}, // 7Y
        {"91282CHE4", 0.080}, // 10Y
        {"912810TF9", 0.150}, // 20Y
        {"912810TG7", 0.200}  // 30Y
    };

    return pv01.at(cusip);
}

void BondRiskService::AddPosition(Position<Bond>& position)
{
    const string cusip = position.GetProduct().GetProductId();

    // Aggregate quantity across all books (TRSY1/TRSY2/TRSY3, etc.).
    // This relies on your Position<T>::GetAggregatePosition() implementation.
    const long totalQty = position.GetAggregatePosition();

    const double pv01 = GetPV01Value(cusip);

    // Create PV01 object for this CUSIP.
    PV01<Bond> pvObj(position.GetProduct(), pv01, totalQty);

    // Insert/update without using operator= (defensive if PV01 is non-assignable).
    const bool existed = (riskMap.find(cusip) != riskMap.end());
    riskMap.erase(cusip);
    map<string, PV01<Bond>>::iterator it = riskMap.emplace(cusip, pvObj).first;
    PV01<Bond>& stored = it->second;

    // Recompute bucket risks BEFORE notifying listeners,
    // so listeners can query up-to-date bucketed PV01.
    ComputeBucketRisk();

    // Notify listeners of add/update.
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}

const PV01<BucketedSector<Bond>>&
BondRiskService::GetBucketedRisk(const BucketedSector<Bond>& sector) const
{
    return bucketRiskMap.at(sector.GetName());
}

const PV01<BucketedSector<Bond>>&
BondRiskService::GetBucketedRiskByName(const string& sectorName) const
{
    return bucketRiskMap.at(sectorName);
}

void BondRiskService::ComputeBucketRisk()
{
    // Build bucket sectors once and reuse them.
    // ProductLookup::GetBond returns a reference to a stable Treasury/Bond instance.
    static BucketedSector<Bond> front(
        { ProductLookup::GetBond("91282CGW5"), ProductLookup::GetBond("91282CGZ8") },
        "FrontEnd"
    );

    static BucketedSector<Bond> belly(
        { ProductLookup::GetBond("91282CHA2"),
          ProductLookup::GetBond("91282CHD6"),
          ProductLookup::GetBond("91282CHE4") },
        "Belly"
    );

    static BucketedSector<Bond> longend(
        { ProductLookup::GetBond("912810TF9"), ProductLookup::GetBond("912810TG7") },
        "LongEnd"
    );

    BucketedSector<Bond>* sectors[] = { &front, &belly, &longend };

    for (BucketedSector<Bond>* sec : sectors)
    {
        double totalRisk = 0.0;

        // Sum PV01 * quantity across all products in the sector.
        for (const Bond& b : sec->GetProducts())
        {
            const string pcusip = b.GetProductId();
            auto it = riskMap.find(pcusip);
            if (it != riskMap.end())
            {
                const PV01<Bond>& r = it->second;
                totalRisk += r.GetPV01() * static_cast<double>(r.GetQuantity());
            }
        }

        PV01<BucketedSector<Bond>> bucket(*sec, totalRisk, 1);

        // Update bucketRiskMap entry without relying on assignment.
        const string name = sec->GetName();
        bucketRiskMap.erase(name);
        bucketRiskMap.emplace(name, bucket);
    }
}
