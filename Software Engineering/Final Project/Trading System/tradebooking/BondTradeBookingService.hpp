/**
 * BondTradeBookingService.hpp
 * Trade booking service for US Treasury bonds.
 *
 * This service receives Trade<Bond> objects from an inbound connector and stores
 * them in memory keyed by trade id. It notifies downstream listeners (e.g. PositionService)
 * via the ServiceListener callback chain.
 *
 * @author Hao Wang
 */
#ifndef BOND_TRADE_BOOKING_SERVICE_HPP
#define BOND_TRADE_BOOKING_SERVICE_HPP

#include "../base/soa.hpp"
#include "../products/TreasuryProducts.hpp"
#include "../base/tradebookingservice.hpp"

#include <map>
#include <vector>
#include <string>

 /**
  * BondTradeBookingService
  * Concrete implementation of TradeBookingService<Bond>.
  */
class BondTradeBookingService : public TradeBookingService<Bond>
{
public:
    BondTradeBookingService();

    /**
     * Get a stored trade by trade id.
     * Throws std::out_of_range if key not found.
     */
    virtual Trade<Bond>& GetData(std::string key) override;

    /**
     * Receive a new / updated trade and notify listeners.
     * This is typically invoked by BookTrade() or by a connector.
     */
    virtual void OnMessage(Trade<Bond>& data) override;

    /**
     * Register a listener (PositionService listener, historical, etc.).
     */
    virtual void AddListener(ServiceListener< Trade<Bond> >* listener) override;

    /**
     * Return all registered listeners.
     */
    virtual const std::vector< ServiceListener< Trade<Bond> >* >& GetListeners() const override;

    /**
     * Book the trade (required by base interface).
     * This method copies the const input into a mutable Trade and routes through OnMessage().
     */
    virtual void BookTrade(const Trade<Bond>& trade);

private:
    std::map<std::string, Trade<Bond> > tradeMap;
    std::vector<ServiceListener< Trade<Bond> >*> listeners;
};

#endif
