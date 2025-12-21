// ====================== BondAlgoStreamingService.cpp ======================
#include "BondAlgoStreamingService.hpp"
#include <iostream>

BondAlgoStreamingService::BondAlgoStreamingService()
    : toggleSize(true)
{
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

    const double mid = p.GetMid();
    const double spread = p.GetBidOfferSpread();
    const double half = 0.5 * spread;

    const double bidPx = mid - half;
    const double askPx = mid + half;

    const long visible = toggleSize ? 1'000'000L : 2'000'000L;
    const long hidden = visible * 2;

    toggleSize = !toggleSize;

    PriceStreamOrder bid(bidPx, visible, hidden, PricingSide::BID);
    PriceStreamOrder ask(askPx, visible, hidden, PricingSide::OFFER);

    PriceStream<Bond> stream(product, bid, ask);
    
    const bool existed = (streamMap.find(cusip) != streamMap.end());
    streamMap.erase(cusip);
    auto it = streamMap.emplace(cusip, stream).first;

    PriceStream<Bond>& stored = it->second;
    
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}
