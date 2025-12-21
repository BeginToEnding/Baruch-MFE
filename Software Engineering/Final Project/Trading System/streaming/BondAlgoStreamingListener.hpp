// ====================== BondAlgoStreamingListener.hpp ======================
#ifndef BOND_ALGO_STREAMING_LISTENER_HPP
#define BOND_ALGO_STREAMING_LISTENER_HPP

#include "BondAlgoStreamingService.hpp"

class BondAlgoStreamingListener : public ServiceListener< Price<Bond> >
{
public:
    BondAlgoStreamingListener(BondAlgoStreamingService* s) : algo(s) {}

    virtual void ProcessAdd(Price<Bond>& p) override {
        algo->ProcessPrice(p);
    }
    virtual void ProcessRemove(Price<Bond>& p) override {}
    virtual void ProcessUpdate(Price<Bond>& p) override {}

private:
    BondAlgoStreamingService* algo;
};

#endif
