/**
 * BondAlgoExecutionListener.hpp
 * Listener that forwards OrderBook<Bond> updates into BondAlgoExecutionService.
 *
 * Typically registered on BondMarketDataService.
 *
 * @author Hao Wang
 */

#ifndef BOND_ALGO_EXECUTION_LISTENER_HPP
#define BOND_ALGO_EXECUTION_LISTENER_HPP

#include "BondAlgoExecutionService.hpp"

 /**
  * BondAlgoExecutionListener
  * Receives market data updates and triggers algo execution logic.
  */
class BondAlgoExecutionListener : public ServiceListener< OrderBook<Bond> >
{
public:
    /**
     * @param e Target algo-execution service.
     */
    BondAlgoExecutionListener(BondAlgoExecutionService* e) : algo(e) {}

    /**
     * On new market data, run algo execution logic.
     */
    virtual void ProcessAdd(OrderBook<Bond>& ob) override
    {
        algo->ProcessMarketData(ob);
    }

    virtual void ProcessRemove(OrderBook<Bond>& /*ob*/) override {}
    virtual void ProcessUpdate(OrderBook<Bond>& /*ob*/) override {}

private:
    BondAlgoExecutionService* algo;
};

#endif
