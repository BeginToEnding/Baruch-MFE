/**
 * BondInquiryListener.hpp
 * A simple listener registered on BondInquiryService.
 *
 * When it receives an Inquiry in RECEIVED state, it triggers auto-quoting:
 * SendQuote(inquiryId, 100.0).
 *
 * @author Hao Wang
 */

#ifndef BOND_INQUIRY_LISTENER_HPP
#define BOND_INQUIRY_LISTENER_HPP

#include "BondInquiryService.hpp"

using namespace std;

/**
 * BondInquiryListener
 * Auto-quotes inquiries as required by assignment.
 */
class BondInquiryListener : public ServiceListener< Inquiry<Bond> >
{
public:
    /**
     * @param s Target service to call SendQuote().
     */
    BondInquiryListener(BondInquiryService* s)
        : service(s)
    {}

    /**
     * On first receipt of an inquiry, quote it at price 100.
     */
    virtual void ProcessAdd(Inquiry<Bond>& inq) override
    {
        if (inq.GetState() == InquiryState::RECEIVED)
        {
            // Assignment: always quote 100 for RECEIVED.
            service->SendQuote(inq.GetInquiryId(), 100.0);
        }
    }

    virtual void ProcessRemove(Inquiry<Bond>& /*inq*/) override {}
    virtual void ProcessUpdate(Inquiry<Bond>& /*inq*/) override {}

private:
    BondInquiryService* service;
};

#endif
