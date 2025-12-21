// ====================== BondStreamingService.hpp ======================
#ifndef BOND_STREAMING_SERVICE_HPP
#define BOND_STREAMING_SERVICE_HPP

#include "../base/soa.hpp"
#include "../base/streamingservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include <map>
#include <vector>

class BondStreamingService : public StreamingService<Bond>
{
public:
    BondStreamingService();

    virtual PriceStream<Bond>& GetData(string key) override;
    virtual void OnMessage(PriceStream<Bond>& data) override;

    virtual void AddListener(ServiceListener< PriceStream<Bond> >* listener) override;
    virtual const vector<ServiceListener< PriceStream<Bond> >*>&
        GetListeners() const override;

    virtual void PublishPrice(PriceStream<Bond>& stream);

    void SetConnector(Connector< PriceStream<Bond> >* c);

private:
    map<string, PriceStream<Bond>> streams;
    vector<ServiceListener< PriceStream<Bond> >*> listeners;

    Connector< PriceStream<Bond> >* connector;
};

#endif
