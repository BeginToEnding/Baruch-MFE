// ====================== BondInquiryService.cpp ======================
#include "BondInquiryService.hpp"
#include <iostream>
#include <stdexcept>

BondInquiryService::BondInquiryService()
    : connector(nullptr)
{
    // No product lookup initialization needed here.
    // Inquiry messages carry the Bond product already.
}

Inquiry<Bond>& BondInquiryService::GetData(string key)
{
    return inquiries.at(key);
}

void BondInquiryService::AddListener(ServiceListener<Inquiry<Bond>>* l)
{
    listeners.push_back(l);
}

const vector<ServiceListener<Inquiry<Bond>>*>& BondInquiryService::GetListeners() const
{
    return listeners;
}

void BondInquiryService::SetConnector(Connector<Inquiry<Bond>>* c)
{
    connector = c;
}

void BondInquiryService::OnMessage(Inquiry<Bond>& data)
{
    const string id = data.GetInquiryId();
    const bool existed = (inquiries.find(id) != inquiries.end());

    // Store inquiry (avoid operator[] and operator= pitfalls)
    inquiries.erase(id);
    auto it = inquiries.emplace(id, data).first;
    Inquiry<Bond>& stored = it->second;

    // Notify listeners
    for (auto* l : listeners)
    {
        if (!existed) l->ProcessAdd(stored);
        else          l->ProcessUpdate(stored);
    }
}

void BondInquiryService::SendQuote(const string& inquiryId, double price)
{
    if (!connector) return;

    auto it = inquiries.find(inquiryId);
    if (it == inquiries.end())
    {
        std::cerr << "[InquiryService] SendQuote: inquiryId not found: " << inquiryId << "\n";
        return;
    }

    Inquiry<Bond>& original = it->second;

    Inquiry<Bond> quoted(
        inquiryId,
        original.GetProduct(),
        original.GetSide(),
        original.GetQuantity(),
        price,
        InquiryState::QUOTED
    );
    
    Inquiry<Bond> tmp = quoted;
    connector->Publish(tmp);
}

void BondInquiryService::RejectInquiry(const string& inquiryId)
{
    if (!connector) return;

    auto it = inquiries.find(inquiryId);
    if (it == inquiries.end())
    {
        std::cerr << "[InquiryService] RejectInquiry: inquiryId not found: " << inquiryId << "\n";
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
