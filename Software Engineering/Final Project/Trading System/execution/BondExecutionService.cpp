// ====================== BondExecutionService.cpp ======================
#include "BondExecutionService.hpp"
#include <iostream>

BondExecutionService::BondExecutionService()
    : connector(nullptr), bookIndex(0)
{
}

ExecutionOrder<Bond>& BondExecutionService::GetData(string key)
{
    // Do NOT use operator[] here: it may default-construct and insert garbage.
    return execMap.at(key);
}

void BondExecutionService::AddListener(ServiceListener<ExecutionOrder<Bond>>* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener<ExecutionOrder<Bond>>*>& BondExecutionService::GetListeners() const
{
    return listeners;
}

void BondExecutionService::OnMessage(ExecutionOrder<Bond>& data)
{
    const string orderId = data.GetOrderId();
    const bool existed = (execMap.find(orderId) != execMap.end());
    
    execMap.erase(orderId);
    auto it = execMap.emplace(orderId, data).first;

    ExecutionOrder<Bond>& stored = it->second;

    // Notify downstream listeners (e.g., Execution->Trade listener)
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }

    if (connector)
    {
        connector->Publish(stored);
    }
}

void BondExecutionService::ExecuteOrder(const ExecutionOrder<Bond>& order, Market market)
{
    (void)market;

    ExecutionOrder<Bond> tmp = order;
    OnMessage(tmp);
}
