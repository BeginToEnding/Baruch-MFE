/**
 * BondTradeBookingService.cpp
 * Implementation of the trade booking service.
 *
 * @author Hao Wang
 */
#include "BondTradeBookingService.hpp"

using std::string;
using std::vector;

BondTradeBookingService::BondTradeBookingService() = default;

Trade<Bond>& BondTradeBookingService::GetData(string key)
{
    return tradeMap.at(key);
}

void BondTradeBookingService::OnMessage(Trade<Bond>& data)
{
    const string id = data.GetTradeId();
    const bool existed = (tradeMap.find(id) != tradeMap.end());

    // Ensure the stored snapshot is updated even when the key already exists.
    tradeMap.erase(id);
    typename std::map<string, Trade<Bond> >::iterator it = tradeMap.emplace(id, data).first;

    Trade<Bond>& stored = it->second;

    // Notify listeners with the stored object reference.
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}

void BondTradeBookingService::AddListener(ServiceListener< Trade<Bond> >* listener)
{
    listeners.push_back(listener);
}

const vector<ServiceListener< Trade<Bond> >*>& BondTradeBookingService::GetListeners() const
{
    return listeners;
}

void BondTradeBookingService::BookTrade(const Trade<Bond>& trade)
{
    // Base interface uses const&, but OnMessage requires a mutable reference.
    Trade<Bond> t(trade);
    OnMessage(t);
}
