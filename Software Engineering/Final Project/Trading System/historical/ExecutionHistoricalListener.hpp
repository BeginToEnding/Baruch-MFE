#ifndef BOND_EXECUTION_HISTORICAL_LISTENER_HPP
#define BOND_EXECUTION_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/executionservice.hpp"
#include "BondHistoricalDataService.hpp"

class BondExecutionHistoricalListener : public ServiceListener< ExecutionOrder<Bond> >
{
public:
    explicit BondExecutionHistoricalListener(BondHistoricalDataService<ExecutionOrder<Bond>>* hs)
        : hist(hs) {}

    void ProcessAdd(ExecutionOrder<Bond>& o) override { hist->PersistData(o.GetOrderId(), o); }
    void ProcessUpdate(ExecutionOrder<Bond>& o) override { hist->PersistData(o.GetOrderId(), o); }
    void ProcessRemove(ExecutionOrder<Bond>&) override {}

private:
    BondHistoricalDataService<ExecutionOrder<Bond>>* hist;
};

#endif
