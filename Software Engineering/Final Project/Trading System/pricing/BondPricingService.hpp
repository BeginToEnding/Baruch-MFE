/**
 * BondPricingService.hpp
 * Pricing service for US Treasury bonds.
 *
 * This service receives Price<Bond> updates from a Connector (socket feed)
 * and notifies downstream listeners (AlgoStreaming, GUI throttle, etc.).
 *
 * @author Hao Wang
 */
#ifndef BOND_PRICING_SERVICE_HPP
#define BOND_PRICING_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/soa.hpp"
#include "../base/pricingservice.hpp"

#include <map>
#include <vector>
#include <string>

 /**
  * BondPricingService
  * Stores the latest Price<Bond> for each product (keyed by CUSIP).
  */
class BondPricingService : public PricingService<Bond>
{
public:
    BondPricingService();

    /**
     * Get the stored price for a given key (CUSIP).
     * Throws if key not found.
     */
    virtual Price<Bond>& GetData(std::string key) override;

    /**
     * Receive a new price update (from connector or internal call).
     * Updates internal map and notifies listeners via ProcessAdd/ProcessUpdate.
     */
    virtual void OnMessage(Price<Bond>& data) override;

    /**
     * Register a listener to receive price callbacks.
     */
    virtual void AddListener(ServiceListener< Price<Bond> >* listener) override;

    /**
     * Return all registered listeners.
     */
    virtual const std::vector< ServiceListener< Price<Bond> >* >& GetListeners() const override;

    /**
     * Convenience method: update using CUSIP + decimal mid + decimal spread.
     * Caller should already have converted fractional input to decimal.
     */
    void UpdatePrice(const std::string& cusip, double mid, double spread);

private:
    std::map<std::string, Price<Bond>> priceMap;
    std::vector<ServiceListener< Price<Bond> >*> listeners;
};

#endif
