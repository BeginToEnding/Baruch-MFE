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
 * Generic historical service for data type T.
 * It persists incoming objects via a type-specific Connector<T>.
 */
template<typename T>
class BondHistoricalDataService : public HistoricalDataService<T>
{
public:
    BondHistoricalDataService() : connector(nullptr) {}

    void SetConnector(Connector<T>* c) { connector = c; }

    // --- Service interface required by SOA base ---
    T& GetData(string key) override { return dataMap.at(key); }

    // Historical service is typically a sink: we persist via PersistData called by listeners.
    void OnMessage(T& /*data*/) override {}

    void AddListener(ServiceListener<T>* l) override { listeners.push_back(l); }

    const vector<ServiceListener<T>*>& GetListeners() const override { return listeners; }

    // --- HistoricalDataService interface ---
    void PersistData(string persistKey, const T& data) override
    {
        // Keep latest snapshot keyed by persistKey (CUSIP, orderId, inquiryId, etc.)
        dataMap.erase(persistKey);
        dataMap.emplace(persistKey, data);

        if (connector)
        {
            T tmp = data;
            connector->Publish(tmp);
        }
    }

private:
    map<string, T> dataMap;
    vector<ServiceListener<T>*> listeners;
    Connector<T>* connector;
};

#endif
