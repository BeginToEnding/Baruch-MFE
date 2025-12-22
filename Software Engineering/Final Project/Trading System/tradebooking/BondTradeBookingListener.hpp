/**
 * BondTradeBookingListener.hpp
 * Example no-op listener for trade booking events.
 *
 * @author Hao Wang
 */
#ifndef BOND_TRADE_BOOKING_LISTENER_HPP
#define BOND_TRADE_BOOKING_LISTENER_HPP

#include "BondTradeBookingService.hpp"

 /**
  * BondTradeBookingListener
  * No-op placeholder. Real wiring typically uses BondTradeToPositionListener.
  */
class BondTradeBookingListener : public ServiceListener< Trade<Bond> >
{
public:
    BondTradeBookingListener() = default;

    virtual void ProcessAdd(Trade<Bond>& /*data*/) override {}
    virtual void ProcessRemove(Trade<Bond>& /*data*/) override {}
    virtual void ProcessUpdate(Trade<Bond>& /*data*/) override {}
};

#endif
