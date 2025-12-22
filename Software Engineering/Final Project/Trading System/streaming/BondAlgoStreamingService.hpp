/**
 * BondAlgoStreamingService.hpp
 * Defines BondAlgoStreamingService, which converts PricingService Price<Bond>
 * updates into bid/offer PriceStream<Bond> objects for the StreamingService.
 *
 * This module is the "algo-streaming" layer:
 *   PricingService (Price) -> AlgoStreaming (PriceStream) -> StreamingService
 *
 * Requirements:
 * - Alternate visible size between 1,000,000 and 2,000,000 each update.
 * - Hidden size is always 2x visible size.
 *
 * @author Hao Wang
 */

#ifndef BOND_ALGO_STREAMING_SERVICE_HPP
#define BOND_ALGO_STREAMING_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../base/pricingservice.hpp"
#include "../base/streamingservice.hpp"
#include "../base/soa.hpp"

#include <map>
#include <vector>
#include <string>

using namespace std;

/**
 * BondAlgoStreamingService
 * Keyed by product id (CUSIP). Value is the latest PriceStream<Bond>.
 */
class BondAlgoStreamingService : public Service<string, PriceStream<Bond>>
{
public:
    /**
     * Construct the algo-streaming service.
     */
    BondAlgoStreamingService();

    /**
     * Get the latest stream for a given CUSIP.
     */
    virtual PriceStream<Bond>& GetData(string key) override;

    /**
     * Not used: this service is driven by incoming Price<Bond> from PricingService.
     */
    virtual void OnMessage(PriceStream<Bond>& /*data*/) override {}

    /**
     * Register a listener that consumes PriceStream<Bond> outputs.
     */
    virtual void AddListener(ServiceListener< PriceStream<Bond> >* listener) override;

    /**
     * Return registered listeners.
     */
    virtual const vector<ServiceListener< PriceStream<Bond> >*>&
        GetListeners() const override;

    /**
     * Convert a Price<Bond> into a PriceStream<Bond> and notify listeners.
     *
     * @param price Latest mid/spread from PricingService.
     */
    void ProcessPrice(const Price<Bond>& price);

private:
    // Latest stream per CUSIP
    map<string, PriceStream<Bond>> streamMap;

    // Downstream listeners (typically algo->streaming bridge, historical, etc.)
    vector<ServiceListener< PriceStream<Bond> >*> listeners;

    // Toggle visible size: 1MM -> 2MM -> 1MM -> ...
    bool toggleSize;
};

#endif
