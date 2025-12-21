// ====================== BondPositionService.hpp ======================
#ifndef BOND_POSITION_SERVICE_HPP
#define BOND_POSITION_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/positionservice.hpp"
#include "../base/tradebookingservice.hpp"
#include "../base/soa.hpp"
#include <map>

class BondPositionService : public PositionService<Bond>
{
public:
    BondPositionService();

    // return Position object
    virtual Position<Bond>& GetData(string key) override;

    // new trade from TradeBookingService
    virtual void OnMessage(Position<Bond>& data) override {}

    // listener management
    virtual void AddListener(ServiceListener< Position<Bond> >* listener) override;
    virtual const vector<ServiceListener< Position<Bond> >*>& GetListeners() const override;

    // AddTrade from base class
    virtual void AddTrade(const Trade<Bond>& trade) override;

private:
    map<string, Position<Bond>> positions;
    vector<ServiceListener< Position<Bond> >*> listeners;
};

#endif
