/**
 * BondExecutionService.cpp
 * Implements the execution service for U.S. Treasury bonds.
 *
 * The execution service receives execution orders from the algo-execution layer,
 * stores them, notifies listeners (e.g., execution-to-trade), and optionally
 * publishes executions out via a socket connector to an external subscriber.
 *
 * @author Hao Wang
 */

#include "BondExecutionService.hpp"
#include <iostream>

using namespace std;

BondExecutionService::BondExecutionService()
    : connector(nullptr), bookIndex(0)
{
    // bookIndex is used by downstream chain (e.g., trade generation) to cycle books.
}

ExecutionOrder<Bond>& BondExecutionService::GetData(string key)
{
    // Do NOT use operator[] here: it may default-construct and insert a dummy object.
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

    // ExecutionOrder<T> may be non-assignable in some implementations;
    // erase + emplace avoids relying on operator=.
    execMap.erase(orderId);
    map<string, ExecutionOrder<Bond>>::iterator it = execMap.emplace(orderId, data).first;

    // Use stored object to guarantee stable lifetime for listeners.
    ExecutionOrder<Bond>& stored = it->second;

    // Notify downstream listeners (e.g., BondExecutionToTradeListener).
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }

    // Publish execution out to external subscriber (if configured).
    if (connector)
    {
        connector->Publish(stored);
    }
}

void BondExecutionService::ExecuteOrder(const ExecutionOrder<Bond>& order, Market market)
{
    // The assignment spec only requires execution on a given market,
    // but our simplified implementation does not differentiate markets.
    (void)market;

    // Create a mutable copy so we can pass through OnMessage() signature.
    ExecutionOrder<Bond> tmp(order);
    OnMessage(tmp);
}
