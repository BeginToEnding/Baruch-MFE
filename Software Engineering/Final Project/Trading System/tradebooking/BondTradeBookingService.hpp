// ====================== BondTradeBookingService.hpp ======================
#ifndef BOND_TRADE_BOOKING_SERVICE_HPP
#define BOND_TRADE_BOOKING_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/ProductLookup.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/Books.hpp"
#include "../base/soa.hpp"
#include "../base/tradebookingservice.hpp"
#include <map>
#include <vector>

class BondTradeBookingService : public TradeBookingService<Bond>
{
public:
    BondTradeBookingService();

    // Get trade memory
    virtual Trade<Bond>& GetData(string key) override;

    // Handle new trade pushed by connector
    virtual void OnMessage(Trade<Bond>& data) override;

    // Add listener
    virtual void AddListener(ServiceListener< Trade<Bond> >* listener) override;

    // Return listeners
    virtual const vector< ServiceListener< Trade<Bond> >* >& GetListeners() const override;

    // BookTrade required by base class
    virtual void BookTrade(const Trade<Bond>& trade);

private:
    map<string, Trade<Bond>> tradeMap;
    vector<ServiceListener< Trade<Bond> >*> listeners;
};

#endif
