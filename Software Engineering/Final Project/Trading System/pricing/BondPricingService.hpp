// ====================== BondPricingService.hpp ======================
#ifndef BOND_PRICING_SERVICE_HPP
#define BOND_PRICING_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/soa.hpp"
#include "../base/pricingservice.hpp"
#include <map>

class BondPricingService : public PricingService<Bond>
{
public:
    BondPricingService();

    // Get stored price
    virtual Price<Bond>& GetData(string key) override;

    // Receive new price update
    virtual void OnMessage(Price<Bond>& data) override;

    // Add listener
    virtual void AddListener(ServiceListener< Price<Bond> >* listener) override;

    // Get listeners
    virtual const vector< ServiceListener< Price<Bond> >* >& GetListeners() const override;

    // Convenience method: update using CUSIP + mid + spread
    void UpdatePrice(const string& cusip, double mid, double spread);

private:
    map<string, Price<Bond>> priceMap;
    vector<ServiceListener< Price<Bond> >*> listeners;
};

#endif
