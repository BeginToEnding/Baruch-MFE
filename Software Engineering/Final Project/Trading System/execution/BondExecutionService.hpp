/**
 * BondExecutionService.hpp
 * Defines BondExecutionService, which stores and publishes ExecutionOrder<Bond>.
 *
 * @author Hao Wang
 */

#ifndef BOND_EXECUTION_SERVICE_HPP
#define BOND_EXECUTION_SERVICE_HPP

#include "../base/executionservice.hpp"
#include "../base/soa.hpp"
#include "../products/TreasuryProducts.hpp"

#include <vector>
#include <map>
#include <string>

using namespace std;

/**
 * BondExecutionService
 * Stores execution orders keyed by order id, notifies listeners, and
 * publishes out via a connector if configured.
 */
class BondExecutionService : public ExecutionService<Bond>
{
public:
    /**
     * Construct the service.
     */
    BondExecutionService();

    /**
     * Execute an order on a given market.
     * In this project we simply store + notify + publish.
     *
     * @param order  Execution order from algo-execution layer.
     * @param market Market enum (kept for interface compatibility).
     */
    void ExecuteOrder(const ExecutionOrder<Bond>& order, Market market);

    /**
     * Retrieve an execution order by its key (order id).
     */
    ExecutionOrder<Bond>& GetData(string key) override;

    /**
     * Receive an execution order update (typically from ExecuteOrder()).
     */
    void OnMessage(ExecutionOrder<Bond>& data) override;

    /**
     * Add a downstream listener (e.g., execution-to-trade, historical, etc.).
     */
    void AddListener(ServiceListener<ExecutionOrder<Bond>>* l) override;

    /**
     * Get all registered listeners.
     */
    const vector<ServiceListener<ExecutionOrder<Bond>>*>& GetListeners() const override;

    /**
     * Set outbound connector to publish executions to an external subscriber.
     */
    void SetConnector(Connector<ExecutionOrder<Bond>>* c) { connector = c; }

    /**
     * Expose current book cycling index if needed by a listener.
     * (Optional utility; safe for single-threaded listener chain.)
     */
    int& GetBookIndex() { return bookIndex; }

private:
    map<string, ExecutionOrder<Bond>> execMap;
    vector<ServiceListener<ExecutionOrder<Bond>>*> listeners;

    Connector<ExecutionOrder<Bond>>* connector;

    // Book index used for round-robin book assignment in the execution->trade chain.
    int bookIndex;
};

#endif
