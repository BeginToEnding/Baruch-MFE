/**
 * BondInquiryService.cpp
 * Implements BondInquiryService: store inquiries, notify listeners, and publish
 * quote/reject responses through connector.
 *
 * @author Hao Wang
 */

#include "BondInquiryService.hpp"
#include <iostream>

using namespace std;

BondInquiryService::BondInquiryService()
    : connector(nullptr)
{
    // This service is populated by BondInquiryConnector::Start().
}

Inquiry<Bond>& BondInquiryService::GetData(string key)
{
    return inquiries.at(key);
}

void BondInquiryService::AddListener(ServiceListener< Inquiry<Bond> >* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener< Inquiry<Bond> >*>& BondInquiryService::GetListeners() const
{
    return listeners;
}

void BondInquiryService::SetConnector(Connector< Inquiry<Bond> >* c)
{
    connector = c;
}

void BondInquiryService::OnMessage(Inquiry<Bond>& data)
{
    const string id = data.GetInquiryId();
    const bool existed = (inquiries.find(id) != inquiries.end());

    // Store latest inquiry snapshot.
    inquiries.erase(id);
    map<string, Inquiry<Bond> >::iterator it = inquiries.emplace(id, data).first;
    Inquiry<Bond>& stored = it->second;

    // Notify listeners (e.g., BondInquiryListener auto-quote).
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}

void BondInquiryService::SendQuote(const string& inquiryId, double price)
{
    if (!connector) return;

    // Make sure inquiry exists.
    map<string, Inquiry<Bond> >::iterator it = inquiries.find(inquiryId);
    if (it == inquiries.end())
    {
        cerr << "[InquiryService] SendQuote: inquiryId not found: " << inquiryId << "\n";
        return;
    }

    Inquiry<Bond>& original = it->second;

    // Create a quoted inquiry object.
    Inquiry<Bond> quoted(
        inquiryId,
        original.GetProduct(),
        original.GetSide(),
        original.GetQuantity(),
        price,                 // decimal internal
        InquiryState::QUOTED
    );

    // Connector expects a non-const ref, so publish a mutable temp.
    Inquiry<Bond> tmp = quoted;
    connector->Publish(tmp);
}

void BondInquiryService::RejectInquiry(const string& inquiryId)
{
    if (!connector) return;

    map<string, Inquiry<Bond> >::iterator it = inquiries.find(inquiryId);
    if (it == inquiries.end())
    {
        cerr << "[InquiryService] RejectInquiry: inquiryId not found: " << inquiryId << "\n";
        return;
    }

    Inquiry<Bond>& original = it->second;

    Inquiry<Bond> rej(
        inquiryId,
        original.GetProduct(),
        original.GetSide(),
        original.GetQuantity(),
        original.GetPrice(),
        InquiryState::REJECTED
    );

    Inquiry<Bond> tmp = rej;
    connector->Publish(tmp);
}
