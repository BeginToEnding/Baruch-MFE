#ifndef BOND_STREAMING_HISTORICAL_LISTENER_HPP
#define BOND_STREAMING_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/streamingservice.hpp"
#include "BondHistoricalDataService.hpp"

class BondStreamingHistoricalListener : public ServiceListener< PriceStream<Bond> >
{
public:
    explicit BondStreamingHistoricalListener(BondHistoricalDataService<PriceStream<Bond>>* hs)
        : hist(hs) {}

    void ProcessAdd(PriceStream<Bond>& s) override { hist->PersistData(s.GetProduct().GetProductId(), s); }
    void ProcessUpdate(PriceStream<Bond>& s) override { hist->PersistData(s.GetProduct().GetProductId(), s); }
    void ProcessRemove(PriceStream<Bond>&) override {}

private:
    BondHistoricalDataService<PriceStream<Bond>>* hist;
};

#endif
