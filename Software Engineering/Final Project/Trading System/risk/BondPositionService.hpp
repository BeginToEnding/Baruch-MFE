/**
 * BondPositionService.hpp
 * Position service implementation for US Treasury bonds.
 *
 * The position service is updated by trades from BondTradeBookingService via a ServiceListener.
 * It maintains per-CUSIP positions split by book (TRSY1/TRSY2/TRSY3) and supports aggregate
 * position calculation through Position<T>::GetAggregatePosition().
 *
 * @author Hao Wang
 */

#ifndef BOND_POSITION_SERVICE_HPP
#define BOND_POSITION_SERVICE_HPP

#include "../base/positionservice.hpp"
#include "../base/tradebookingservice.hpp"
#include "../base/soa.hpp"
#include "../products/TreasuryProducts.hpp"

#include <map>
#include <vector>
#include <string>

using namespace std;

/**
 * BondPositionService
 * Maintains Position<Bond> objects keyed by CUSIP, updated from trades.
 */
class BondPositionService : public PositionService<Bond>
{
public:
    /**
     * Construct a BondPositionService.
     * Positions are trade-driven; no inbound connector is required.
     */
    BondPositionService();

    /**
     * Get Position object by product identifier (CUSIP).
     *
     * @param key CUSIP
     * @return reference to Position<Bond>
     */
    virtual Position<Bond>& GetData(string key) override;

    /**
     * No inbound connector calls OnMessage for Position in this project.
     * Positions are produced from AddTrade(). Therefore OnMessage is a no-op.
     */
    virtual void OnMessage(Position<Bond>& /*data*/) override {}

    /**
     * Register a listener for position updates.
     *
     * @param listener listener to be notified on add/update
     */
    virtual void AddListener(ServiceListener< Position<Bond> >* listener) override;

    /**
     * Get all registered listeners.
     *
     * @return vector of listeners
     */
    virtual const vector<ServiceListener< Position<Bond> >*>& GetListeners() const override;

    /**
     * Add a trade to the position service.
     * This updates the appropriate book position, and then notifies listeners.
     *
     * @param trade Trade<Bond> from the trade booking service
     */
    virtual void AddTrade(const Trade<Bond>& trade) override;

private:
    /// Positions keyed by CUSIP.
    map<string, Position<Bond>> positions;

    /// Registered listeners for position updates.
    vector<ServiceListener< Position<Bond> >*> listeners;
};

#endif
