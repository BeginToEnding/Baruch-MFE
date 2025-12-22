/**
 * BondAlgoStreamingToStreamingListener.hpp
 * Listener that bridges PriceStream<Bond> outputs from BondAlgoStreamingService
 * into BondStreamingService via PublishPrice().
 *
 * Per assignment, AlgoStreaming should call StreamingService::PublishPrice().
 *
 * @author Hao Wang
 */

#ifndef BOND_ALGO_STREAMING_TO_STREAMING_LISTENER_HPP
#define BOND_ALGO_STREAMING_TO_STREAMING_LISTENER_HPP

#include "../base/soa.hpp"
#include "BondStreamingService.hpp"

 /**
  * BondAlgoStreamingToStreamingListener
  * Bridges: AlgoStreamingService -> StreamingService
  */
class BondAlgoStreamingToStreamingListener : public ServiceListener< PriceStream<Bond> >
{
public:
    /**
     * @param service Target streaming service.
     */
    BondAlgoStreamingToStreamingListener(BondStreamingService* service)
        : streamService(service) {}

    /**
     * Publish the stream into StreamingService.
     */
    virtual void ProcessAdd(PriceStream<Bond>& ps) override
    {
        streamService->PublishPrice(ps);
    }

    virtual void ProcessUpdate(PriceStream<Bond>& ps) override
    {
        streamService->PublishPrice(ps);
    }

    virtual void ProcessRemove(PriceStream<Bond>& /*ps*/) override {}

private:
    BondStreamingService* streamService;
};

#endif
