/**
 * BondPricingListener.hpp
 * Example listener for Price<Bond> events from BondPricingService.
 * Currently a no-op placeholder.
 *
 * @author Hao Wang
 */
#ifndef BOND_PRICING_LISTENER_HPP
#define BOND_PRICING_LISTENER_HPP

#include "BondPricingService.hpp"

 /**
  * BondPricingListener
  * No-op listener template (can be extended for debugging/logging).
  * In the trading system, real listeners are AlgoStreaming and GUI throttle listeners.
  */
class BondPricingListener : public ServiceListener< Price<Bond> >
{
public:
    BondPricingListener() = default;

    virtual void ProcessAdd(Price<Bond>& /*data*/) override {}
    virtual void ProcessRemove(Price<Bond>& /*data*/) override {}
    virtual void ProcessUpdate(Price<Bond>& /*data*/) override {}
};

#endif
