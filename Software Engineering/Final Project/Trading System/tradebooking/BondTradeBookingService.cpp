// ====================== BondTradeBookingService.cpp ======================
#include "BondTradeBookingService.hpp"
#include <iostream>

BondTradeBookingService::BondTradeBookingService() = default;

Trade<Bond>& BondTradeBookingService::GetData(string key)
{
    return tradeMap.at(key);
}

void BondTradeBookingService::OnMessage(Trade<Bond>& data)
{
    const string id = data.GetTradeId();

    const bool existed = (tradeMap.find(id) != tradeMap.end());

    auto it = tradeMap.emplace(id, data).first;

    Trade<Bond>& stored = it->second;

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
    Trade<Bond> t(trade);
    OnMessage(t);
}
