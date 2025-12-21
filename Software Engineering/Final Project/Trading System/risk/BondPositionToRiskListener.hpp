// ====================== BondPositionToRiskListener.hpp ======================
#ifndef BOND_POSITION_TO_RISK_LISTENER_HPP
#define BOND_POSITION_TO_RISK_LISTENER_HPP

#include "BondRiskService.hpp"
#include "BondPositionService.hpp"

class BondPositionToRiskListener : public ServiceListener< Position<Bond> >
{
public:
    BondPositionToRiskListener(BondRiskService* rs) : riskService(rs) {}

    virtual void ProcessAdd(Position<Bond>& pos) override {
        riskService->AddPosition(pos);
    }
    virtual void ProcessRemove(Position<Bond>& pos) override {}
    virtual void ProcessUpdate(Position<Bond>& pos) override {}

private:
    BondRiskService* riskService;
};

#endif
