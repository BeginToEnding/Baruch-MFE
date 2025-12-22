/**
 * BondStreamingHistoricalListener.hpp
 * Listener that subscribes to BondStreamingService and persists PriceStream<Bond>
 * snapshots into BondHistoricalDataService.
 *
 * @author Hao Wang
 */

#ifndef BOND_STREAMING_HISTORICAL_LISTENER_HPP
#define BOND_STREAMING_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/streamingservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "BondHistoricalDataService.hpp"

 /**
  * BondStreamingHistoricalListener
  * Persists streaming snapshots keyed by product id (CUSIP).
  */
class BondStreamingHistoricalListener : public ServiceListener< PriceStream<Bond> >
{
public:
    /**
     * @param hs Historical service for PriceStream<Bond>.
     */
    explicit BondStreamingHistoricalListener(BondHistoricalDataService< PriceStream<Bond> >* hs)
        : hist(hs)
    {
    }

    void ProcessAdd(PriceStream<Bond>& s) override
    {
        hist->PersistData(s.GetProduct().GetProductId(), s);
    }

    void ProcessUpdate(PriceStream<Bond>& s) override
    {
        hist->PersistData(s.GetProduct().GetProductId(), s);
    }

    void ProcessRemove(PriceStream<Bond>&) override {}

private:
    BondHistoricalDataService< PriceStream<Bond> >* hist;
};

#endif
