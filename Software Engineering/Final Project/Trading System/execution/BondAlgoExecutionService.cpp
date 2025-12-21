// ====================== BondAlgoExecutionService.cpp ======================
#include "BondAlgoExecutionService.hpp"
#include <iostream>
#include <cmath>

BondAlgoExecutionService::BondAlgoExecutionService()
    : nextBuy(true), orderCounter(1)
{
    // This service only reacts to incoming market data (OrderBook<Bond>).
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

static inline bool NearlyEqual(double a, double b, double eps = 1e-12)
{
    return std::fabs(a - b) <= eps;
}

void BondAlgoExecutionService::ProcessMarketData(const OrderBook<Bond>& ob)
{
    const Bond& product = ob.GetProduct();
    const string cusip = product.GetProductId();

    const auto& bidStack = ob.GetBidStack();
    const auto& askStack = ob.GetOfferStack();

    // Defensive: ensure there is at least one level on both sides.
    if (bidStack.empty() || askStack.empty())
        return;

    const double bestBid = bidStack.front().GetPrice();
    const double bestAsk = askStack.front().GetPrice();
    const double spread = bestAsk - bestBid;

    // Only trade when top-of-book spread is exactly 1/128.
    const double minSpread = 1.0 / 128.0;
    if (!NearlyEqual(spread, minSpread))
        return;

    // Determine trade direction (alternating BUY/SELL).
    PricingSide side;
    double px = 0.0;
    long qty = 0;

    if (nextBuy)
    {
        // BUY: cross to the offer
        side = PricingSide::BID;
        px = bestAsk;
        qty = askStack.front().GetQuantity();
    }
    else
    {
        // SELL: cross to the bid
        side = PricingSide::OFFER;
        px = bestBid;
        qty = bidStack.front().GetQuantity();
    }

    nextBuy = !nextBuy;

    const string orderId = "ALGEXEC_" + std::to_string(orderCounter++);

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

    // Store execution order.
    const bool existed = (algoMap.find(orderId) != algoMap.end());
    algoMap.erase(orderId);
    auto it = algoMap.emplace(orderId, exec).first;
    
    ExecutionOrder<Bond>& stored = it->second;
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}
