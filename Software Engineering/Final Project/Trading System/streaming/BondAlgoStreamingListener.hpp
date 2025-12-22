/**
 * BondAlgoStreamingListener.hpp
 * Listener that forwards PricingService Price<Bond> updates into
 * BondAlgoStreamingService::ProcessPrice().
 *
 * Typically registered on BondPricingService.
 *
 * @author Hao Wang
 */

#ifndef BOND_ALGO_STREAMING_LISTENER_HPP
#define BOND_ALGO_STREAMING_LISTENER_HPP

#include "BondAlgoStreamingService.hpp"

 /**
  * BondAlgoStreamingListener
  * Bridges: PricingService -> AlgoStreamingService
  */
class BondAlgoStreamingListener : public ServiceListener< Price<Bond> >
{
public:
    /**
     * @param s Target algo-streaming service.
     */
    BondAlgoStreamingListener(BondAlgoStreamingService* s) : algo(s) {}

    /**
     * On a new price update, generate/refresh streams.
     */
    virtual void ProcessAdd(Price<Bond>& p) override
    {
        algo->ProcessPrice(p);
    }

    virtual void ProcessRemove(Price<Bond>& /*p*/) override {}
    virtual void ProcessUpdate(Price<Bond>& /*p*/) override {}

private:
    BondAlgoStreamingService* algo;
};

#endif
