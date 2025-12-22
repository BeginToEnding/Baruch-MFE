/**
 * BondPositionToRiskListener.hpp
 * Listener that forwards Position updates into the BondRiskService.
 *
 * This is the linkage required by the project specification:
 *   BondPositionService -> (ServiceListener) -> BondRiskService::AddPosition()
 *
 * @author Hao Wang
 */

#ifndef BOND_POSITION_TO_RISK_LISTENER_HPP
#define BOND_POSITION_TO_RISK_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/positionservice.hpp"

#include "BondRiskService.hpp"

 /**
  * BondPositionToRiskListener
  * Forwards both add and update events to the risk service, ensuring risk is kept current.
  */
class BondPositionToRiskListener : public ServiceListener< Position<Bond> >
{
public:
    /**
     * Construct listener with a target risk service.
     *
     * @param rs pointer to BondRiskService (owned/managed elsewhere, typically in main)
     */
    explicit BondPositionToRiskListener(BondRiskService* rs) : riskService(rs) {}

    /// When a new position is created, compute/update risk.
    virtual void ProcessAdd(Position<Bond>& pos) override
    {
        riskService->AddPosition(pos);
    }

    /// When an existing position changes, compute/update risk as well.
    virtual void ProcessUpdate(Position<Bond>& pos) override
    {
        riskService->AddPosition(pos);
    }

    virtual void ProcessRemove(Position<Bond>& /*pos*/) override {}

private:
    BondRiskService* riskService;
};

#endif
