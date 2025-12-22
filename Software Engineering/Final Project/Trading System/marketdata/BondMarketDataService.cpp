/**
 * BondMarketDataService.cpp
 * Implementation of BondMarketDataService.
 *
 * @author Hao Wang
 */

#include "BondMarketDataService.hpp"

BondMarketDataService::BondMarketDataService() = default;

OrderBook<Bond>& BondMarketDataService::GetData(string key)
{
    // at() throws if key does not exist; caller should ensure availability.
    return books.at(key);
}

void BondMarketDataService::OnMessage(OrderBook<Bond>& data)
{
    const string cusip = data.GetProduct().GetProductId();
    const bool existed = (books.find(cusip) != books.end());

    // Defensive: avoid operator= in case OrderBook is non-assignable.
    books.erase(cusip);
    map<string, OrderBook<Bond>>::iterator it = books.emplace(cusip, data).first;

    // Use stored object so listeners see an object with stable lifetime.
    OrderBook<Bond>& stored = it->second;

    // Update cached best bid/offer if both stacks are non-empty.
    const vector<Order>& bidStack = stored.GetBidStack();
    const vector<Order>& offerStack = stored.GetOfferStack();
    if (!bidStack.empty() && !offerStack.empty())
    {
        bestLevels.erase(cusip);
        bestLevels.emplace(cusip, BidOffer(bidStack.front(), offerStack.front()));
    }

    // Notify listeners: add for first time, update afterwards.
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}

void BondMarketDataService::AddListener(ServiceListener<OrderBook<Bond>>* listener)
{
    listeners.push_back(listener);
}

const vector<ServiceListener<OrderBook<Bond>>*>& BondMarketDataService::GetListeners() const
{
    return listeners;
}

const BidOffer& BondMarketDataService::GetBestBidOffer(const string& productId)
{
    return bestLevels.at(productId);
}

const OrderBook<Bond>& BondMarketDataService::AggregateDepth(const string& productId)
{
    // The project interface calls it "AggregateDepth"; here we simply return full depth.
    return books.at(productId);
}

/**
 * Helper to construct a 5x5 order book and push it into the service.
 *
 * - mid is expected to oscillate between 99 and 101 in 1/256 increments (done by feeder/generator).
 * - spread is the top-of-book bid/offer spread (oscillates 1/128 -> ... -> 1/32 -> ... -> 1/128).
 * - deeper levels widen by the smallest tick (1/256) each level.
 *
 * Level sizes:
 *   L1=10MM, L2=20MM, L3=30MM, L4=40MM, L5=50MM.
 */
void BondMarketDataService::BuildAndSendOrderBook(
    const string& cusip,
    double mid,
    double topSpread
)
{
    // Product lookup: Treasury derives from Bond, so we can store as Bond.
    const Treasury& product = ProductLookup::GetBond(cusip);

    static const long sizes[5] = {
        10000000L, 20000000L, 30000000L, 40000000L, 50000000L
    };

    // US Treasuries trade in 1/256 increments.
    const double tick = 1.0 / 256.0;

    vector<Order> bids;
    vector<Order> offers;
    bids.reserve(5);
    offers.reserve(5);

    // Level i uses spread_i = topSpread + i * tick (widening by smallest increment).
    for (int i = 0; i < 5; ++i)
    {
        const double spread_i = topSpread + static_cast<double>(i) * tick;
        const double half_i = 0.5 * spread_i;

        const double bidPx = mid - half_i;
        const double askPx = mid + half_i;

        bids.emplace_back(bidPx, sizes[i], PricingSide::BID);
        offers.emplace_back(askPx, sizes[i], PricingSide::OFFER);
    }

    OrderBook<Bond> ob(product, bids, offers);
    OnMessage(ob);
}
