/**
 * BondPricingService.cpp
 * Implementation of BondPricingService.
 *
 * @author Hao Wang
 */
#include "BondPricingService.hpp"

BondPricingService::BondPricingService() = default;

Price<Bond>& BondPricingService::GetData(std::string key)
{
    // Throws std::out_of_range if key not found, which is fine for this project.
    return priceMap.at(key);
}

void BondPricingService::OnMessage(Price<Bond>& data)
{
    // Use productId (CUSIP) as key
    const std::string cusip = data.GetProduct().GetProductId();

    // Track whether this is an add vs update event
    const bool existed = (priceMap.find(cusip) != priceMap.end());

    // Replace stored snapshot
    priceMap.erase(cusip);
    auto it = priceMap.emplace(cusip, data).first;

    // Notify listeners using the stored object reference
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

const std::vector<ServiceListener< Price<Bond> >*>& BondPricingService::GetListeners() const
{
    return listeners;
}

void BondPricingService::UpdatePrice(const std::string& cusip, double mid, double spread)
{
    // Lookup product by CUSIP; Treasury inherits Bond so it can be used where Bond is expected.
    const Treasury& t = ProductLookup::GetBond(cusip);

    // Store internally in decimal form (fractional only at file/socket boundaries)
    Price<Bond> p(t, mid, spread);

    // Route through OnMessage so we keep one update path
    OnMessage(p);
}
