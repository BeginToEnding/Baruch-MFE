// ====================== BondAlgoExecutionService.hpp ======================
#ifndef BOND_ALGO_EXECUTION_SERVICE_HPP
#define BOND_ALGO_EXECUTION_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../utils/Books.hpp"
#include "../base/executionservice.hpp"
#include "../base/marketdataservice.hpp"
#include "../base/soa.hpp"
#include <map>

class BondAlgoExecutionService : public Service<string, ExecutionOrder<Bond>>
{
public:
    BondAlgoExecutionService();

    // Get stored algo execution
    virtual ExecutionOrder<Bond>& GetData(string key) override;

    // Used when ExecutionService confirms exec, but not needed here
    virtual void OnMessage(ExecutionOrder<Bond>& data) override {}

    virtual void AddListener(ServiceListener< ExecutionOrder<Bond> >* listener) override;
    virtual const vector< ServiceListener< ExecutionOrder<Bond> >* >&
        GetListeners() const override;

    // Called from MarketData listener
    void ProcessMarketData(const OrderBook<Bond>& ob);

private:
    map<string, ExecutionOrder<Bond>> algoMap;
    vector<ServiceListener< ExecutionOrder<Bond> >*> listeners;

    bool nextBuy; // toggle BUY/SELL
    int orderCounter;
};

#endif
