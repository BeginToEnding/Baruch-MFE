/**
 * BondPositionService.cpp
 * Implementation of BondPositionService.
 *
 * @author Hao Wang
 */

#include "BondPositionService.hpp"

BondPositionService::BondPositionService() = default;

Position<Bond>& BondPositionService::GetData(string key)
{
    // at() throws if the key does not exist; acceptable if caller ensures existence.
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
    const string cusip = trade.GetProduct().GetProductId();
    const string book = trade.GetBook();

    // Signed quantity: SELL reduces position, BUY increases position.
    long signedQty = trade.GetQuantity();
    if (trade.GetSide() == SELL) signedQty = -signedQty;

    // Insert Position only once; emplace will not overwrite if the key already exists.
    auto res = positions.emplace(cusip, Position<Bond>(trade.GetProduct()));
    map<string, Position<Bond>>::iterator it = res.first;
    const bool inserted = res.second;

    Position<Bond>& pos = it->second;

    // Update the book-level position by delta (positive or negative).
    pos.UpdatePosition(book, signedQty);

    // Notify downstream listeners (e.g., Position -> Risk listener).
    for (auto* l : listeners)
    {
        if (inserted) l->ProcessAdd(pos);
        else          l->ProcessUpdate(pos);
    }
}
