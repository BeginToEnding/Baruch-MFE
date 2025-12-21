#ifndef BOND_STREAMING_HISTORICAL_CONNECTOR_HPP
#define BOND_STREAMING_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/streamingservice.hpp"
#include "../utils/TimeUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

class BondStreamingHistoricalConnector : public Connector< PriceStream<Bond> >
{
public:
    explicit BondStreamingHistoricalConnector(const std::string& file = "streaming.txt")
        : fileName(file) {}

    void Publish(PriceStream<Bond>& s) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[StreamHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        const auto& bid = s.GetBidOrder();
        const auto& ask = s.GetOfferOrder();

        fout << NowTimestampMS() << ","
            << s.GetProduct().GetProductId() << ","
            << "BIDPX=" << bid.GetPrice() << ",BIDVIS=" << bid.GetVisibleQuantity() << ",BIDHID=" << bid.GetHiddenQuantity() << ","
            << "ASKPX=" << ask.GetPrice() << ",ASKVIS=" << ask.GetVisibleQuantity() << ",ASKHID=" << ask.GetHiddenQuantity()
            << "\n";
    }

private:
    std::string fileName;
};

#endif
