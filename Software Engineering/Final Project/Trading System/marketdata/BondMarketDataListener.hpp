// ====================== BondMarketDataListener.hpp ======================
#ifndef BOND_MARKET_DATA_LISTENER_HPP
#define BOND_MARKET_DATA_LISTENER_HPP

#include "BondMarketDataService.hpp"

class BondMarketDataListener : public ServiceListener<OrderBook<Bond>>
{
public:
    BondMarketDataListener() = default;

    virtual void ProcessAdd(OrderBook<Bond>& data) override {}
    virtual void ProcessRemove(OrderBook<Bond>& data) override {}
    virtual void ProcessUpdate(OrderBook<Bond>& data) override {}
};

#endif
