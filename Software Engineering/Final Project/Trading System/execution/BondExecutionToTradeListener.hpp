/**
 * BondExecutionToTradeListener.hpp
 * Listener that converts executions into booked trades and pushes them into
 * BondTradeBookingService.
 *
 * Per assignment, trades should cycle through books: TRSY1 -> TRSY2 -> TRSY3 -> ...
 *
 * @author Hao Wang
 */

#ifndef BOND_EXECUTION_TO_TRADE_LISTENER_HPP
#define BOND_EXECUTION_TO_TRADE_LISTENER_HPP

#include "../base/soa.hpp"
#include "../tradebooking/BondTradeBookingService.hpp"
#include "../utils/Books.hpp"

#include <string>

using namespace std;

/**
 * BondExecutionToTradeListener
 * Converts an execution order into a Trade<Bond> and sends it to the trade booking service.
 */
class BondExecutionToTradeListener : public ServiceListener< ExecutionOrder<Bond> >
{
public:
    /**
     * @param tbs Target trade booking service.
     */
    BondExecutionToTradeListener(BondTradeBookingService* tbs)
        : tradeBookingService(tbs), bookIndex(0) {}

    /**
     * On execution, create a Trade and send it into the trade booking service.
     */
    virtual void ProcessAdd(ExecutionOrder<Bond>& order) override
    {
        // Map PricingSide (execution-side) to Trade side.
        // BID means we bought; OFFER means we sold.
        const PricingSide ps = order.GetSide();
        const Side side = (ps == PricingSide::BID ? BUY : SELL);

        // Cycle books TRSY1/TRSY2/TRSY3 in round-robin order.
        const string book = NextBook(bookIndex);

        // Use order id as trade id for simplicity.
        Trade<Bond> trade(
            order.GetProduct(),
            order.GetOrderId(),          // tradeId
            order.GetPrice(),
            book,
            order.GetVisibleQuantity(),
            side
        );

        // Push through service interface (BookTrade will call OnMessage and notify listeners).
        tradeBookingService->BookTrade(trade);
    }

    virtual void ProcessUpdate(ExecutionOrder<Bond>& /*order*/) override {}
    virtual void ProcessRemove(ExecutionOrder<Bond>& /*order*/) override {}

private:
    BondTradeBookingService* tradeBookingService;

    // Book cycling state is kept inside this listener instance.
    int bookIndex;
};

#endif
