// ====================== GUIService.hpp ======================
#ifndef GUI_SERVICE_HPP
#define GUI_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/TimeUtils.hpp"
#include "../base/soa.hpp"
#include "../base/pricingservice.hpp"

#include <fstream>
#include <map>
#include <vector>
#include <string>
#include <iostream>

class GUIService : public Service<string, Price<Bond>>
{
public:
    GUIService();
    ~GUIService();

    // Receive throttled price updates
    void OnMessage(Price<Bond>& data) override;

    Price<Bond>& GetData(string key) override
    {
        return priceMap.at(key);
    }

    // GUI service is a sink in this project (no downstream listeners)
    void AddListener(ServiceListener<Price<Bond>>* /*l*/) override {}
    const vector<ServiceListener<Price<Bond>>*>& GetListeners() const override
    {
        return emptyListeners;
    }

    bool Finished() const { return count >= kMaxUpdates; }

private:
    static constexpr int kMaxUpdates = 100;

    std::map<string, Price<Bond>> priceMap;
    int count;

    // Keep file handle open for performance
    std::ofstream fout;

    // Required by Service interface
    vector<ServiceListener<Price<Bond>>*> emptyListeners;
};

#endif
