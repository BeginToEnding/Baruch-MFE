/**
 * BondMarketDataListener.hpp
 * Default no-op listener for OrderBook<Bond>.
 *
 * This file is mainly a placeholder for debugging or extension.
 *
 * @author Hao Wang
 */

#ifndef BOND_MARKET_DATA_LISTENER_HPP
#define BOND_MARKET_DATA_LISTENER_HPP

#include "BondMarketDataService.hpp"

 /**
  * BondMarketDataListener
  * No-op implementation; can be extended for logging/testing.
  */
class BondMarketDataListener : public ServiceListener<OrderBook<Bond>>
{
public:
    BondMarketDataListener() = default;

    virtual void ProcessAdd(OrderBook<Bond>& /*data*/) override {}
    virtual void ProcessRemove(OrderBook<Bond>& /*data*/) override {}
    virtual void ProcessUpdate(OrderBook<Bond>& /*data*/) override {}
};

#endif
