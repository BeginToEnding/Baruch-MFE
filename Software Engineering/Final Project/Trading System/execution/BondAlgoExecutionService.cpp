/**
 * BondAlgoExecutionService.cpp
 * Implementation of BondAlgoExecutionService.
 *
 * @author Hao Wang
 */

#include "BondAlgoExecutionService.hpp"
#include <iostream>
#include <cmath>

using namespace std;

/**
 * Compare two doubles with a small tolerance.
 * Helpful for matching tick-based spreads like 1/128 exactly.
 */
static inline bool NearlyEqual(double a, double b, double eps = 1e-12)
{
    return std::fabs(a - b) <= eps;
}

BondAlgoExecutionService::BondAlgoExecutionService()
    : nextBuy(true), orderCounter(1)
{
    // This service reacts only to market data (OrderBook<Bond>).
}

ExecutionOrder<Bond>& BondAlgoExecutionService::GetData(string key)
{
    return algoMap.at(key);
}

void BondAlgoExecutionService::AddListener(ServiceListener<ExecutionOrder<Bond>>* listener)
{
    listeners.push_back(listener);
}

const vector<ServiceListener<ExecutionOrder<Bond>>*>& BondAlgoExecutionService::GetListeners() const
{
    return listeners;
}

void BondAlgoExecutionService::ProcessMarketData(const OrderBook<Bond>& ob)
{
    const Bond& product = ob.GetProduct();

    const vector<Order>& bidStack = ob.GetBidStack();
    const vector<Order>& askStack = ob.GetOfferStack();

    // Defensive: need at least top-of-book on both sides.
    if (bidStack.empty() || askStack.empty())
        return;

    const double bestBid = bidStack.front().GetPrice();
    const double bestAsk = askStack.front().GetPrice();
    const double spread = bestAsk - bestBid;

    // Only trade when top-of-book spread is the tightest (1/128).
    const double minSpread = 1.0 / 128.0;
    if (!NearlyEqual(spread, minSpread))
        return;

    // Determine direction: alternate BUY/SELL and cross the spread.
    PricingSide side;
    double px;
    long qty;

    if (nextBuy)
    {
        // BUY: take the offer (cross to ask).
        side = PricingSide::BID;
        px = bestAsk;
        qty = askStack.front().GetQuantity();
    }
    else
    {
        // SELL: hit the bid (cross to bid).
        side = PricingSide::OFFER;
        px = bestBid;
        qty = bidStack.front().GetQuantity();
    }

    nextBuy = !nextBuy;

    // Create unique order id.
    const string orderId = "ALGEXEC_" + to_string(orderCounter++);

    ExecutionOrder<Bond> exec(
        product,
        side,
        orderId,
        OrderType::MARKET,
        px,
        qty,
        0,      // hidden quantity
        "",     // parent order id
        false   // is child order
    );

    // Store the order (erase+emplace avoids relying on operator=).
    algoMap.erase(orderId);
    map<string, ExecutionOrder<Bond>>::iterator it = algoMap.emplace(orderId, exec).first;

    ExecutionOrder<Bond>& stored = it->second;

    // Fan-out to listeners (typically algo->execution bridge).
    for (auto* l : listeners)
    {
        l->ProcessAdd(stored);
    }
}
