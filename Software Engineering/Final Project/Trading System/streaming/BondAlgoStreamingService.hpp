// ====================== BondAlgoStreamingService.hpp ======================
#ifndef BOND_ALGO_STREAMING_SERVICE_HPP
#define BOND_ALGO_STREAMING_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/PriceUtils.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/pricingservice.hpp"
#include "../base/streamingservice.hpp"
#include "../base/soa.hpp"
#include <map>

class BondAlgoStreamingService
    : public Service<string, PriceStream<Bond>>
{
public:
    BondAlgoStreamingService();

    virtual PriceStream<Bond>& GetData(string key) override;
    virtual void OnMessage(PriceStream<Bond>& data) override {}

    virtual void AddListener(ServiceListener< PriceStream<Bond> >* listener) override;
    virtual const vector<ServiceListener< PriceStream<Bond> >*>&
        GetListeners() const override;

    // Called by Pricing listener
    void ProcessPrice(const Price<Bond>& price);

private:
    map<string, PriceStream<Bond>> streamMap;
    vector<ServiceListener< PriceStream<Bond> >*> listeners;

    bool toggleSize;     // alternate visible size
};

#endif
