#ifndef BOND_POSITION_HISTORICAL_LISTENER_HPP
#define BOND_POSITION_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"
#include "BondHistoricalDataService.hpp"

class BondPositionHistoricalListener : public ServiceListener< Position<Bond> >
{
public:
    explicit BondPositionHistoricalListener(BondHistoricalDataService<Position<Bond>>* hs)
        : hist(hs) {}

    void ProcessAdd(Position<Bond>& p) override { hist->PersistData(p.GetProduct().GetProductId(), p); }
    void ProcessUpdate(Position<Bond>& p) override { hist->PersistData(p.GetProduct().GetProductId(), p); }
    void ProcessRemove(Position<Bond>&) override {}

private:
    BondHistoricalDataService<Position<Bond>>* hist;
};

#endif
