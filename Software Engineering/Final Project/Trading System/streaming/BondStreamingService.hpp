/**
 * BondStreamingService.hpp
 * Defines BondStreamingService, which stores and publishes PriceStream<Bond>.
 *
 * This is the service that would "stream" quotes out to clients.
 * In this project, we publish streams outward via a socket connector.
 *
 * @author Hao Wang
 */

#ifndef BOND_STREAMING_SERVICE_HPP
#define BOND_STREAMING_SERVICE_HPP

#include "../base/soa.hpp"
#include "../base/streamingservice.hpp"
#include "../products/TreasuryProducts.hpp"

#include <map>
#include <vector>
#include <string>

using namespace std;

/**
 * BondStreamingService
 * Stores latest PriceStream per product, notifies internal listeners,
 * and publishes outward via connector.
 */
class BondStreamingService : public StreamingService<Bond>
{
public:
    /**
     * Construct streaming service.
     */
    BondStreamingService();

    /**
     * Get latest stream for a given CUSIP.
     */
    virtual PriceStream<Bond>& GetData(string key) override;

    /**
     * OnMessage is not used for inbound data in this architecture;
     * AlgoStreaming should call PublishPrice().
     */
    virtual void OnMessage(PriceStream<Bond>& data) override;

    /**
     * Add listener (e.g., historical persister).
     */
    virtual void AddListener(ServiceListener< PriceStream<Bond> >* listener) override;

    /**
     * Return registered listeners.
     */
    virtual const vector<ServiceListener< PriceStream<Bond> >*>&
        GetListeners() const override;

    /**
     * Publish a PriceStream into this service:
     * - store
     * - notify listeners
     * - publish outward via connector
     */
    virtual void PublishPrice(PriceStream<Bond>& stream) override;

    /**
     * Set outbound connector (StreamingService -> external subscriber).
     */
    void SetConnector(Connector< PriceStream<Bond> >* c);

private:
    map<string, PriceStream<Bond>> streams;
    vector<ServiceListener< PriceStream<Bond> >*> listeners;

    Connector< PriceStream<Bond> >* connector;
};

#endif
