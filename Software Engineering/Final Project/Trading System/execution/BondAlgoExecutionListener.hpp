// ====================== BondAlgoExecutionListener.hpp ======================
#ifndef BOND_ALGO_EXECUTION_LISTENER_HPP
#define BOND_ALGO_EXECUTION_LISTENER_HPP

#include "BondAlgoExecutionService.hpp"

class BondAlgoExecutionListener : public ServiceListener< OrderBook<Bond> >
{
public:
    BondAlgoExecutionListener(BondAlgoExecutionService* e) : algo(e) {}

    virtual void ProcessAdd(OrderBook<Bond>& ob) override {
        algo->ProcessMarketData(ob);
    }

    virtual void ProcessRemove(OrderBook<Bond>& ob) override {}
    virtual void ProcessUpdate(OrderBook<Bond>& ob) override {}

private:
    BondAlgoExecutionService* algo;
};

#endif
