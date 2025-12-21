// ====================== BondTradeToPositionListener.hpp ======================
#ifndef BOND_TRADE_TO_POSITION_LISTENER_HPP
#define BOND_TRADE_TO_POSITION_LISTENER_HPP

#include "../risk/BondPositionService.hpp"
#include "BondTradeBookingService.hpp"

class BondTradeToPositionListener : public ServiceListener< Trade<Bond> >
{
public:
    BondTradeToPositionListener(BondPositionService* p) : posService(p) {}

    virtual void ProcessAdd(Trade<Bond>& trade) override {
        posService->AddTrade(trade);
    }
    virtual void ProcessRemove(Trade<Bond>& trade) override {}
    virtual void ProcessUpdate(Trade<Bond>& trade) override {}

private:
    BondPositionService* posService;
};

#endif
