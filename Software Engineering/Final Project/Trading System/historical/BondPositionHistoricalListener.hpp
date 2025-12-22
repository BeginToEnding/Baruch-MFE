/**
 * BondPositionHistoricalListener.hpp
 * Listener that subscribes to BondPositionService and persists Position<Bond>
 * snapshots into BondHistoricalDataService.
 *
 * @author Hao Wang
 */

#ifndef BOND_POSITION_HISTORICAL_LISTENER_HPP
#define BOND_POSITION_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "BondHistoricalDataService.hpp"

 /**
  * BondPositionHistoricalListener
  * Persists positions keyed by product id (CUSIP).
  */
class BondPositionHistoricalListener : public ServiceListener< Position<Bond> >
{
public:
    /**
     * @param hs Historical service for Position<Bond>.
     */
    explicit BondPositionHistoricalListener(BondHistoricalDataService< Position<Bond> >* hs)
        : hist(hs)
    {
    }

    void ProcessAdd(Position<Bond>& p) override
    {
        hist->PersistData(p.GetProduct().GetProductId(), p);
    }

    void ProcessUpdate(Position<Bond>& p) override
    {
        hist->PersistData(p.GetProduct().GetProductId(), p);
    }

    void ProcessRemove(Position<Bond>&) override {}

private:
    BondHistoricalDataService< Position<Bond> >* hist;
};

#endif
