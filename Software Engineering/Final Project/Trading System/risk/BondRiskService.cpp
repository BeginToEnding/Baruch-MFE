// ====================== BondRiskService.cpp ======================
#include "BondRiskService.hpp"
#include <iostream>

BondRiskService::BondRiskService() = default;

PV01<Bond>& BondRiskService::GetData(string key)
{
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

    // Aggregate quantity across books.
    long totalQty = position.GetAggregatePosition();

    const double pv01 = GetPV01Value(cusip);

    PV01<Bond> pvObj(position.GetProduct(), pv01, totalQty);

    // Avoid operator= in case PV01<Bond> is non-assignable.
    const bool existed = (riskMap.find(cusip) != riskMap.end());
    riskMap.erase(cusip);
    auto it = riskMap.emplace(cusip, pvObj).first;
    PV01<Bond>& stored = it->second;

    ComputeBucketRisk();

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
    // Build sectors once and reuse. Treasury derives from Bond, so it is usable as Bond.
    static BucketedSector<Bond> front(
        { ProductLookup::GetBond("91282CGW5"),
          ProductLookup::GetBond("91282CGZ8") },
        "FrontEnd"
    );

    static BucketedSector<Bond> belly(
        { ProductLookup::GetBond("91282CHA2"),
          ProductLookup::GetBond("91282CHD6"),
          ProductLookup::GetBond("91282CHE4") },
        "Belly"
    );

    static BucketedSector<Bond> longend(
        { ProductLookup::GetBond("912810TF9"),
          ProductLookup::GetBond("912810TG7") },
        "LongEnd"
    );

    BucketedSector<Bond>* sectors[] = { &front, &belly, &longend };

    for (auto* sec : sectors)
    {
        double totalRisk = 0.0;

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

        const string name = sec->GetName();
        bucketRiskMap.erase(name);
        bucketRiskMap.emplace(name, bucket);
    }
}
