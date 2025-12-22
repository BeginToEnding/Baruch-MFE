/**
 * BondAlgoStreamingService.cpp
 * Implements BondAlgoStreamingService.
 *
 * @author Hao Wang
 */

#include "BondAlgoStreamingService.hpp"

using namespace std;

BondAlgoStreamingService::BondAlgoStreamingService()
    : toggleSize(true)
{
    // toggleSize starts at 1MM for the first update.
}

PriceStream<Bond>& BondAlgoStreamingService::GetData(string key)
{
    return streamMap.at(key);
}

void BondAlgoStreamingService::AddListener(ServiceListener<PriceStream<Bond>>* listener)
{
    listeners.push_back(listener);
}

const vector<ServiceListener<PriceStream<Bond>>*>& BondAlgoStreamingService::GetListeners() const
{
    return listeners;
}

void BondAlgoStreamingService::ProcessPrice(const Price<Bond>& p)
{
    const Bond& product = p.GetProduct();
    const string cusip = product.GetProductId();

    // Mid and bid/offer spread are provided by PricingService.
    const double mid = p.GetMid();
    const double spread = p.GetBidOfferSpread();
    const double half = 0.5 * spread;

    // Derive bid/ask prices around mid.
    const double bidPx = mid - half;
    const double askPx = mid + half;

    // Alternate visible sizes per assignment spec.
    const long visible = toggleSize ? 1000000L : 2000000L;

    // Hidden size is always 2x visible.
    const long hidden = visible * 2;

    // Flip for next update.
    toggleSize = !toggleSize;

    // Build stream orders (one on each side).
    PriceStreamOrder bid(bidPx, visible, hidden, PricingSide::BID);
    PriceStreamOrder ask(askPx, visible, hidden, PricingSide::OFFER);

    // Create the PriceStream container.
    PriceStream<Bond> stream(product, bid, ask);

    // Store latest stream per CUSIP.
    const bool existed = (streamMap.find(cusip) != streamMap.end());
    streamMap.erase(cusip);
    map<string, PriceStream<Bond>>::iterator it = streamMap.emplace(cusip, stream).first;

    // Use stored reference to ensure stable lifetime for listeners.
    PriceStream<Bond>& stored = it->second;

    // Notify downstream listeners.
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}
