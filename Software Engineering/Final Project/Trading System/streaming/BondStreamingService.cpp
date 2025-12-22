/**
 * BondStreamingService.cpp
 * Implements BondStreamingService.
 *
 * @author Hao Wang
 */

#include "BondStreamingService.hpp"

using namespace std;

BondStreamingService::BondStreamingService()
    : connector(nullptr)
{
}

PriceStream<Bond>& BondStreamingService::GetData(string key)
{
    return streams.at(key);
}

void BondStreamingService::OnMessage(PriceStream<Bond>& data)
{
    // In this project, the preferred entry point is PublishPrice().
    // We keep OnMessage for interface completeness and forward to PublishPrice().
    PublishPrice(data);
}

void BondStreamingService::AddListener(ServiceListener< PriceStream<Bond> >* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener< PriceStream<Bond> >*>& BondStreamingService::GetListeners() const
{
    return listeners;
}

void BondStreamingService::PublishPrice(PriceStream<Bond>& stream)
{
    const string cusip = stream.GetProduct().GetProductId();
    const bool existed = (streams.find(cusip) != streams.end());

    // Store latest stream (erase+emplace avoids operator= dependence).
    streams.erase(cusip);
    map<string, PriceStream<Bond>>::iterator it = streams.emplace(cusip, stream).first;

    // Use stored reference to ensure stable lifetime.
    PriceStream<Bond>& stored = it->second;

    // Notify internal listeners (e.g., historical service).
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }

    // Publish outward to external subscriber if configured.
    if (connector)
    {
        connector->Publish(stored);
    }
}

void BondStreamingService::SetConnector(Connector< PriceStream<Bond> >* c)
{
    connector = c;
}
