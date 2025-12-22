/**
 * BondHistoricalDataService.hpp
 * A generic historical data service for persisting objects of type T.
 *
 * Design:
 * - This service is typically a sink: upstream listeners call PersistData().
 * - PersistData() stores the latest snapshot in memory and delegates to a configured
 *   Connector<T> to append into a file (or any other sink).
 *
 * Note:
 * - All price formatting rules should be handled inside the type-specific connector,
 *   so the generic service stays purely generic.
 *
 * @author Hao Wang
 */

#ifndef BOND_HISTORICAL_DATA_SERVICE_HPP
#define BOND_HISTORICAL_DATA_SERVICE_HPP

#include "../base/historicaldataservice.hpp"
#include "../base/soa.hpp"

#include <map>
#include <vector>
#include <string>

using std::string;
using std::map;
using std::vector;

/**
 * BondHistoricalDataService
 * Generic historical service for persisting any type T.
 *
 * Examples of T in this project:
 * - Position<Bond>
 * - RiskLine
 * - ExecutionOrder<Bond>
 * - PriceStream<Bond>
 * - Inquiry<Bond>
 */
template<typename T>
class BondHistoricalDataService : public HistoricalDataService<T>
{
public:
    /**
     * Construct with no connector. You must call SetConnector() before persisting.
     */
    BondHistoricalDataService()
        : connector(nullptr)
    {
    }

    /**
     * Set the persistence connector (file writer).
     * The connector is owned/managed elsewhere (created in main).
     */
    void SetConnector(Connector<T>* c)
    {
        connector = c;
    }

    // ----------------------------
    // Service interface (SOA base)
    // ----------------------------

    /**
     * Get the last stored snapshot for a given key.
     */
    T& GetData(string key) override
    {
        return dataMap.at(key);
    }

    /**
     * Not used: historical service is not typically pushed into via OnMessage().
     * Upstream listeners call PersistData() directly.
     */
    void OnMessage(T& /*data*/) override {}

    /**
     * Listener management (rarely used for a sink, but required by base interface).
     */
    void AddListener(ServiceListener<T>* l) override
    {
        listeners.push_back(l);
    }

    const vector<ServiceListener<T>*>& GetListeners() const override
    {
        return listeners;
    }

    // -----------------------------------
    // HistoricalDataService<T> interface
    // -----------------------------------

    /**
     * Persist the incoming object:
     * - store latest snapshot in memory
     * - publish through connector (append to file)
     *
     * @param persistKey Key to identify the record (CUSIP, orderId, inquiryId, etc.)
     * @param data       Data snapshot to persist
     */
    void PersistData(string persistKey, const T& data) override
    {
        // Keep latest snapshot keyed by persistKey.
        dataMap.erase(persistKey);
        dataMap.emplace(persistKey, data);

        // Delegate to connector if configured.
        if (connector)
        {
            // Connector API takes non-const ref; publish a mutable copy.
            T tmp = data;
            connector->Publish(tmp);
        }
    }

private:
    // In-memory "latest snapshot" cache.
    map<string, T> dataMap;

    // Required by SOA base interface.
    vector<ServiceListener<T>*> listeners;

    // Type-specific persistence sink (file writer).
    Connector<T>* connector;
};

#endif
