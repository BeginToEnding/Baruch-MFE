/**
 * BondMarketDataService.hpp
 * Market data service implementation for US Treasury bonds.
 *
 * This service stores full depth order books keyed by CUSIP and provides:
 *  - best bid/offer (top of book)
 *  - aggregate depth (here simply returning the stored order book)
 *
 * The service is populated by an inbound connector that reads marketdata.txt
 * and pushes updates via socket into the system.
 *
 * @author Hao Wang
 */

#ifndef BOND_MARKET_DATA_SERVICE_HPP
#define BOND_MARKET_DATA_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/marketdataservice.hpp"
#include "../base/soa.hpp"

#include <map>
#include <vector>

using namespace std;

/**
 * BondMarketDataService
 * Stores and updates OrderBook<Bond> objects and notifies listeners.
 */
class BondMarketDataService : public MarketDataService<Bond>
{
public:
    /**
     * Construct a BondMarketDataService.
     */
    BondMarketDataService();

    /**
     * Get an OrderBook by product id (CUSIP).
     *
     * @param key CUSIP
     * @return reference to stored OrderBook
     */
    virtual OrderBook<Bond>& GetData(string key) override;

    /**
     * Receive a new order book update and notify listeners.
     *
     * @param data incoming OrderBook (typically constructed by the connector)
     */
    virtual void OnMessage(OrderBook<Bond>& data) override;

    /**
     * Register a listener for order book updates.
     */
    virtual void AddListener(ServiceListener< OrderBook<Bond> >* listener) override;

    /**
     * Return all registered listeners.
     */
    virtual const vector<ServiceListener< OrderBook<Bond> >*>& GetListeners() const override;

    /**
     * Return current best bid/offer for a product.
     *
     * @param productId CUSIP
     * @return BidOffer object (top of book)
     */
    virtual const BidOffer& GetBestBidOffer(const string& productId) override;

    /**
     * Return the current aggregate depth for a product.
     * In this project, we keep and return the full order book.
     *
     * @param productId CUSIP
     * @return stored OrderBook (full depth)
     */
    virtual const OrderBook<Bond>& AggregateDepth(const string& productId) override;

    /**
     * Helper: build a 5x5 order book from mid and top-of-book spread and push it into the service.
     *
     * @param cusip     CUSIP for the Treasury
     * @param mid       mid price in decimal (internally we use decimal)
     * @param spread    top-of-book bid/offer spread in decimal
     */
    void BuildAndSendOrderBook(const string& cusip, double mid, double spread);

private:
    /// Full order books keyed by CUSIP.
    map<string, OrderBook<Bond>> books;

    /// Cached best bid/offer keyed by CUSIP.
    map<string, BidOffer> bestLevels;

    /// Registered listeners that consume order book updates.
    vector<ServiceListener<OrderBook<Bond>>*> listeners;
};

#endif
