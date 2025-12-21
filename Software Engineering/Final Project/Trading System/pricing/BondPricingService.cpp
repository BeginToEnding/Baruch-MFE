// ====================== BondPricingService.cpp ======================
#include "BondPricingService.hpp"
#include "../utils/ProductLookup.hpp"

BondPricingService::BondPricingService() = default;

Price<Bond>& BondPricingService::GetData(string key)
{
    return priceMap.at(key);
}

void BondPricingService::OnMessage(Price<Bond>& data)
{
    const string cusip = data.GetProduct().GetProductId();
    
    const bool existed = (priceMap.find(cusip) != priceMap.end());

    priceMap.erase(cusip);
    auto it = priceMap.emplace(cusip, data).first;
    
    Price<Bond>& stored = it->second;

    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}

void BondPricingService::AddListener(ServiceListener< Price<Bond> >* listener)
{
    listeners.push_back(listener);
}

const vector<ServiceListener< Price<Bond> >*>& BondPricingService::GetListeners() const
{
    return listeners;
}

void BondPricingService::UpdatePrice(const string& cusip, double mid, double spread)
{
    const Treasury& t = ProductLookup::GetBond(cusip);
    
    Price<Bond> p(t, mid, spread);

    OnMessage(p);
}
