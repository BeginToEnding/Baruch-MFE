// ====================== BondPricingListener.hpp ======================
#ifndef BOND_PRICING_LISTENER_HPP
#define BOND_PRICING_LISTENER_HPP

#include "BondPricingService.hpp"

class BondPricingListener : public ServiceListener< Price<Bond> >
{
public:
    BondPricingListener() = default;

    virtual void ProcessAdd(Price<Bond>& data) override {}
    virtual void ProcessRemove(Price<Bond>& data) override {}
    virtual void ProcessUpdate(Price<Bond>& data) override {}
};

#endif
