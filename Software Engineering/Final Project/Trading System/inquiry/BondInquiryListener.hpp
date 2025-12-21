// ====================== BondInquiryListener.hpp ======================
#ifndef BOND_INQUIRY_LISTENER_HPP
#define BOND_INQUIRY_LISTENER_HPP

#include "BondInquiryService.hpp"

class BondInquiryListener : public ServiceListener< Inquiry<Bond> >
{
public:
    BondInquiryListener(BondInquiryService* s)
        : service(s) {}

    virtual void ProcessAdd(Inquiry<Bond>& inq) override
    {
        if (inq.GetState() == InquiryState::RECEIVED)
        {
            service->SendQuote(inq.GetInquiryId(), 100.0);
        }
    }

    virtual void ProcessRemove(Inquiry<Bond>& inq) override {}
    virtual void ProcessUpdate(Inquiry<Bond>& inq) override {}

private:
    BondInquiryService* service;
};

#endif
