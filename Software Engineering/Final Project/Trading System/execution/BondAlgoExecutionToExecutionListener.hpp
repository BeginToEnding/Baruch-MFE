#ifndef BOND_ALGO_EXECUTION_TO_EXECUTION_LISTENER_HPP
#define BOND_ALGO_EXECUTION_TO_EXECUTION_LISTENER_HPP

#include "../base/soa.hpp"
#include "BondExecutionService.hpp"

class BondAlgoExecutionToExecutionListener
    : public ServiceListener< ExecutionOrder<Bond> >
{
public:
    BondAlgoExecutionToExecutionListener(BondExecutionService* service)
        : execService(service) {}

    virtual void ProcessAdd(ExecutionOrder<Bond>& order) override
    {
        execService->OnMessage(order);
    }

    virtual void ProcessUpdate(ExecutionOrder<Bond>& order) override
    {
        execService->OnMessage(order);
    }

    virtual void ProcessRemove(ExecutionOrder<Bond>& order) override {}

private:
    BondExecutionService* execService;
};

#endif
