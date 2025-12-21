// ====================== BondStreamingService.cpp ======================
#include "BondStreamingService.hpp"

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
    const string cusip = data.GetProduct().GetProductId();
    const bool existed = (streams.find(cusip) != streams.end());

    // Store
    streams.erase(cusip);
    auto it = streams.emplace(cusip, data).first;
    PriceStream<Bond>& stored = it->second;

    // Notify listeners
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }

    PublishPrice(stored);
}

void BondStreamingService::AddListener(
    ServiceListener< PriceStream<Bond> >* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener< PriceStream<Bond> >*>&
BondStreamingService::GetListeners() const
{
    return listeners;
}

void BondStreamingService::PublishPrice(PriceStream<Bond>& stream)
{
    if (connector)
        connector->Publish(stream);
}

void BondStreamingService::SetConnector(Connector< PriceStream<Bond> >* c)
{
    connector = c;
}
