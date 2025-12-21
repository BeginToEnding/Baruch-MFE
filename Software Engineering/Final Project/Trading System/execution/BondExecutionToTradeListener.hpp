#ifndef BOND_EXECUTION_TO_TRADE_LISTENER_HPP
#define BOND_EXECUTION_TO_TRADE_LISTENER_HPP

#include "../base/soa.hpp"
#include "../tradebooking/BondTradeBookingService.hpp"

class BondExecutionToTradeListener
    : public ServiceListener< ExecutionOrder<Bond> >
{
public:
    BondExecutionToTradeListener(BondTradeBookingService* tbs)
        : tradeBookingService(tbs) {}

    virtual void ProcessAdd(ExecutionOrder<Bond>& order) override
    {
        PricingSide ps = order.GetSide();
        Side side = (ps == BID ? BUY : SELL);

        // how to determine the book?
        string book = "TRSY1";
        Trade<Bond> trade(order.GetProduct(),
            order.GetOrderId(),             // tradeId
            order.GetPrice(),
            book,
            order.GetVisibleQuantity(),
            side);

        tradeBookingService->OnMessage(trade);
    }

    virtual void ProcessUpdate(ExecutionOrder<Bond>& order) override {}
    virtual void ProcessRemove(ExecutionOrder<Bond>& order) override {}

private:
    BondTradeBookingService* tradeBookingService;
};

#endif
