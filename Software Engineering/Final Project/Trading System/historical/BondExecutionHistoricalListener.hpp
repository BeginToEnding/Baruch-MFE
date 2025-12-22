/**
 * BondExecutionHistoricalListener.hpp
 * Listener that subscribes to BondExecutionService and persists ExecutionOrder<Bond>
 * objects into the historical service.
 *
 * @author Hao Wang
 */

#ifndef BOND_EXECUTION_HISTORICAL_LISTENER_HPP
#define BOND_EXECUTION_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/executionservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "BondHistoricalDataService.hpp"

 /**
  * BondExecutionHistoricalListener
  * Persists executions for auditing / downstream analysis.
  */
class BondExecutionHistoricalListener : public ServiceListener< ExecutionOrder<Bond> >
{
public:
    /**
     * @param hs Historical service that persists ExecutionOrder snapshots.
     */
    explicit BondExecutionHistoricalListener(BondHistoricalDataService< ExecutionOrder<Bond> >* hs)
        : hist(hs)
    {
    }

    void ProcessAdd(ExecutionOrder<Bond>& o) override
    {
        // Persist keyed by order id so we keep the latest snapshot per order.
        hist->PersistData(o.GetOrderId(), o);
    }

    void ProcessUpdate(ExecutionOrder<Bond>& o) override
    {
        hist->PersistData(o.GetOrderId(), o);
    }

    void ProcessRemove(ExecutionOrder<Bond>&) override {}

private:
    BondHistoricalDataService< ExecutionOrder<Bond> >* hist;
};

#endif
