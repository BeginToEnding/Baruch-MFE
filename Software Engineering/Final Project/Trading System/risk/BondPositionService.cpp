// ====================== BondPositionService.cpp ======================
#include "BondPositionService.hpp"
#include <iostream>

BondPositionService::BondPositionService() = default;

Position<Bond>& BondPositionService::GetData(string key)
{
    return positions.at(key);
}

void BondPositionService::AddListener(ServiceListener< Position<Bond> >* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener< Position<Bond> >*>& BondPositionService::GetListeners() const
{
    return listeners;
}

void BondPositionService::AddTrade(const Trade<Bond>& trade)
{
    string cusip = trade.GetProduct().GetProductId();
    string book = trade.GetBook();

    // Signed quantity: SELL reduces position, BUY increases position.
    long signedQty = trade.GetQuantity();
    if (trade.GetSide() == SELL) signedQty = -signedQty;

    // Insert Position only once; avoid operator= on Position if it is non-assignable.
    auto res = positions.emplace(cusip, Position<Bond>(trade.GetProduct()));
    auto it = res.first;
    bool inserted = res.second;
    Position<Bond>& pos = it->second;

    // Update this book.
    long oldVal = pos.GetPosition(book);
    pos.UpdatePosition(book, signedQty);

    // Notify downstream listeners (e.g., RiskService listener chain).
    for (auto* l : listeners)
    {
        if (inserted) l->ProcessAdd(pos);
        else          l->ProcessUpdate(pos);
    }
}
