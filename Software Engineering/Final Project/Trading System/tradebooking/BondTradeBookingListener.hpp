// ====================== BondTradeBookingListener.hpp ======================
#ifndef BOND_TRADE_BOOKING_LISTENER_HPP
#define BOND_TRADE_BOOKING_LISTENER_HPP

#include "BondTradeBookingService.hpp"

class BondTradeBookingListener : public ServiceListener< Trade<Bond> >
{
public:
    BondTradeBookingListener() = default;

    virtual void ProcessAdd(Trade<Bond>& data) override {}
    virtual void ProcessRemove(Trade<Bond>& data) override {}
    virtual void ProcessUpdate(Trade<Bond>& data) override {}
};

#endif
