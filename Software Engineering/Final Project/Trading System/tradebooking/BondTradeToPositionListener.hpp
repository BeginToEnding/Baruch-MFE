/**
 * BondTradeToPositionListener.hpp
 * Listener bridging TradeBookingService -> PositionService.
 *
 * This listener registers on BondTradeBookingService and forwards trades into
 * BondPositionService::AddTrade(), without creating explicit service coupling
 * inside the services themselves.
 *
 * @author Hao Wang
 */
#ifndef BOND_TRADE_TO_POSITION_LISTENER_HPP
#define BOND_TRADE_TO_POSITION_LISTENER_HPP

#include "../base/soa.hpp"
#include "../risk/BondPositionService.hpp"

 /**
  * BondTradeToPositionListener
  * Forwards trade events to the position service.
  */
class BondTradeToPositionListener : public ServiceListener< Trade<Bond> >
{
public:
    explicit BondTradeToPositionListener(BondPositionService* p) : posService(p) {}

    virtual void ProcessAdd(Trade<Bond>& trade) override
    {
        if (posService) posService->AddTrade(trade);
    }

    virtual void ProcessRemove(Trade<Bond>& /*trade*/) override {}
    virtual void ProcessUpdate(Trade<Bond>& /*trade*/) override {}

private:
    BondPositionService* posService;
};

#endif
