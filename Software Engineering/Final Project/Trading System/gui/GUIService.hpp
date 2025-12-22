/**
 * GUIService.hpp
 * A lightweight "GUI" sink that consumes throttled Price<Bond> updates
 * and writes a small sample of them to gui.txt.
 *
 * Notes:
 * - This service is a sink: it does not fan out to downstream listeners.
 * - Internally stores the latest Price per CUSIP for potential lookup.
 * - Uses fractional format when writing Mid/Spread to file (assignment requirement).
 *
 * @author Hao Wang
 */

#ifndef GUI_SERVICE_HPP
#define GUI_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/TimeUtils.hpp"
#include "../utils/PriceUtils.hpp"
#include "../base/soa.hpp"
#include "../base/pricingservice.hpp"

#include <fstream>
#include <map>
#include <vector>
#include <string>
#include <iostream>

using namespace std;

/**
 * GUIService
 * Receives (throttled) prices and persists a small number of updates to gui.txt.
 * Keyed by product identifier (CUSIP).
 */
class GUIService : public Service<string, Price<Bond> >
{
public:
    /**
     * Construct GUI service and open gui.txt in append mode.
     */
    GUIService();

    /**
     * Destructor closes the output stream if still open.
     */
    ~GUIService();

    /**
     * Receive a new throttled price update.
     * This is called by GUIThrottleListener (registered on BondPricingService).
     *
     * @param data Price update (mid/spread are in decimal internally).
     */
    void OnMessage(Price<Bond>& data) override;

    /**
     * Get the last cached Price for a given CUSIP.
     */
    Price<Bond>& GetData(string key) override
    {
        return priceMap.at(key);
    }

    /**
     * GUI service is a sink in this project (no downstream listeners).
     */
    void AddListener(ServiceListener< Price<Bond> >* /*l*/) override {}

    /**
     * Required by Service interface; returns an empty listener list.
     */
    const vector<ServiceListener< Price<Bond> >*>& GetListeners() const override
    {
        return emptyListeners;
    }

    /**
     * Whether GUI already logged the maximum number of updates.
     */
    bool Finished() const { return count >= kMaxUpdates; }

private:
    /**
     * Max number of GUI lines to write (assignment requirement: first 100).
     */
    static const int kMaxUpdates = 100;

    // Latest Price per CUSIP (internal storage is decimal)
    map<string, Price<Bond> > priceMap;

    // Number of updates written so far
    int count;

    // Keep file handle open for performance (avoid open/close per line)
    ofstream fout;

    // Required by Service interface
    vector<ServiceListener< Price<Bond> >*> emptyListeners;
};

#endif
