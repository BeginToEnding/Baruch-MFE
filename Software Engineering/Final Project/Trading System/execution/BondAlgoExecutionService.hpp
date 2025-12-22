/**
 * BondAlgoExecutionService.hpp
 * Defines BondAlgoExecutionService, which consumes OrderBook<Bond> updates and
 * generates execution orders when the spread is tightest (1/128).
 *
 * @author Hao Wang
 */

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
#include <vector>
#include <string>

using namespace std;

/**
 * BondAlgoExecutionService
 * Listens to market data (order books) and decides when to aggress top-of-book.
 * Alternates BUY/SELL and only crosses when top spread is exactly 1/128.
 */
class BondAlgoExecutionService : public Service<string, ExecutionOrder<Bond> >
{
public:
    /**
     * Construct the algo-execution service.
     */
    BondAlgoExecutionService();

    /**
     * Return stored execution order (keyed by order id).
     */
    virtual ExecutionOrder<Bond>& GetData(string key) override;

    /**
     * Not used in this simplified design (execution confirmations not fed back here).
     */
    virtual void OnMessage(ExecutionOrder<Bond>& /*data*/) override {}

    /**
     * Add downstream listener (typically algo->execution bridge).
     */
    virtual void AddListener(ServiceListener< ExecutionOrder<Bond> >* listener) override;

    /**
     * Get listeners.
     */
    virtual const vector< ServiceListener< ExecutionOrder<Bond> >* >&
        GetListeners() const override;

    /**
     * Consume market data and potentially generate an execution order.
     *
     * @param ob Incoming order book update.
     */
    void ProcessMarketData(const OrderBook<Bond>& ob);

private:
    map<string, ExecutionOrder<Bond> > algoMap;
    vector<ServiceListener< ExecutionOrder<Bond> >*> listeners;

    bool nextBuy;      // toggles BUY/SELL each time we execute
    int orderCounter;  // used to generate unique order ids
};

#endif
