// ====================== BondMarketDataService.hpp ======================
#ifndef BOND_MARKET_DATA_SERVICE_HPP
#define BOND_MARKET_DATA_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/marketdataservice.hpp"
#include "../base/soa.hpp"
#include <map>

class BondMarketDataService : public MarketDataService<Bond>
{
public:
    BondMarketDataService();

    // Return stored orderbook
    virtual OrderBook<Bond>& GetData(string key) override;

    // Receive inbound orderbook update
    virtual void OnMessage(OrderBook<Bond>& data) override;

    // Listener management
    virtual void AddListener(ServiceListener< OrderBook<Bond> >* listener) override;
    virtual const vector<ServiceListener< OrderBook<Bond> >*>& GetListeners() const override;

    // Best bid / offer
    virtual const BidOffer& GetBestBidOffer(const string& productId) override;

    // Aggregate depth (just return internal)
    virtual const OrderBook<Bond>& AggregateDepth(const string& productId) override;

    // Helper: update using mid and top spread
    void BuildAndSendOrderBook(const string& cusip, double mid, double spread);

private:
    map<string, OrderBook<Bond>> books;
    map<string, BidOffer> bestLevels;
    vector<ServiceListener<OrderBook<Bond>>*> listeners;
};

#endif
