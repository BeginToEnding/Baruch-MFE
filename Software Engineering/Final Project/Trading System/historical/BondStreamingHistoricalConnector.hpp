/**
 * BondStreamingHistoricalConnector.hpp
 * Connector used by BondHistoricalDataService<PriceStream<Bond>> to persist streaming
 * prices into a file (default: streaming.txt).
 *
 * Prices must be written in Treasury fractional format per assignment requirement.
 *
 * Output format example:
 *   timestamp,cusip,BIDPX=...,BIDVIS=...,BIDHID=...,ASKPX=...,ASKVIS=...,ASKHID=...
 *
 * @author Hao Wang
 */

#ifndef BOND_STREAMING_HISTORICAL_CONNECTOR_HPP
#define BOND_STREAMING_HISTORICAL_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/streamingservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "../utils/TimeUtils.hpp"
#include "../utils/PriceUtils.hpp"

#include <fstream>
#include <iostream>
#include <string>

 /**
  * BondStreamingHistoricalConnector
  * Appends PriceStream snapshots into streaming.txt.
  */
class BondStreamingHistoricalConnector : public Connector< PriceStream<Bond> >
{
public:
    /**
     * @param file Output file path (appended).
     */
    explicit BondStreamingHistoricalConnector(const std::string& file = "streaming.txt")
        : fileName(file)
    {
    }

    /**
     * Append one PriceStream snapshot into file.
     */
    void Publish(PriceStream<Bond>& s) override
    {
        std::ofstream fout(fileName, std::ios::app);
        if (!fout.is_open())
        {
            std::cerr << "[StreamHistConnector] Cannot open " << fileName << "\n";
            return;
        }

        const PriceStreamOrder& bid = s.GetBidOrder();
        const PriceStreamOrder& ask = s.GetOfferOrder();

        // Convert decimal prices to fractional strings for persistence.
        fout << NowTimestampMS() << ","
            << s.GetProduct().GetProductId() << ","
            << "BIDPX=" << DecimalToFractional(bid.GetPrice())
            << ",BIDVIS=" << bid.GetVisibleQuantity()
            << ",BIDHID=" << bid.GetHiddenQuantity()
            << ",ASKPX=" << DecimalToFractional(ask.GetPrice())
            << ",ASKVIS=" << ask.GetVisibleQuantity()
            << ",ASKHID=" << ask.GetHiddenQuantity()
            << "\n";
    }

private:
    std::string fileName;
};

#endif
