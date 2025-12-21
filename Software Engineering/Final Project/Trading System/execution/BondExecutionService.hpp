// ====================== BondExecutionService.hpp ======================
#ifndef BOND_EXECUTION_SERVICE_HPP
#define BOND_EXECUTION_SERVICE_HPP

#include "../base/executionservice.hpp"
#include "../base/soa.hpp"
#include "../products/TreasuryProducts.hpp"
#include <vector>
#include <map>
#include <string>

class BondExecutionService : public ExecutionService<Bond>
{
public:
    BondExecutionService();

    void ExecuteOrder(const ExecutionOrder<Bond>& order, Market market);

    ExecutionOrder<Bond>& GetData(string key) override;
    void OnMessage(ExecutionOrder<Bond>& data) override;

    void AddListener(ServiceListener<ExecutionOrder<Bond>>* l) override;
    const vector<ServiceListener<ExecutionOrder<Bond>>*>& GetListeners() const override;

    // Connector to publish executions
    void SetConnector(Connector<ExecutionOrder<Bond>>* c) { connector = c; }

private:
    map<string, ExecutionOrder<Bond>> execMap;
    vector<ServiceListener<ExecutionOrder<Bond>>*> listeners;
    Connector<ExecutionOrder<Bond>>* connector;

    int bookIndex;
};

#endif
