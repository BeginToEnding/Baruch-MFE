#ifndef BOND_ALGO_STREAMING_TO_STREAMING_LISTENER_HPP
#define BOND_ALGO_STREAMING_TO_STREAMING_LISTENER_HPP

#include "../base/soa.hpp"
#include "../streaming/BondStreamingService.hpp"

class BondAlgoStreamingToStreamingListener
    : public ServiceListener< PriceStream<Bond> >
{
public:
    BondAlgoStreamingToStreamingListener(BondStreamingService* service)
        : streamService(service) {}

    virtual void ProcessAdd(PriceStream<Bond>& ps) override
    {
        streamService->OnMessage(ps);
    }

    virtual void ProcessUpdate(PriceStream<Bond>& ps) override
    {
        streamService->OnMessage(ps);
    }

    virtual void ProcessRemove(PriceStream<Bond>& ps) override {}

private:
    BondStreamingService* streamService;
};

#endif
