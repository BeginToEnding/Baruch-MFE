/**
 * BondInquiryHistoricalListener.hpp
 * Listener that subscribes to BondInquiryService and persists Inquiry<Bond>
 * objects into the historical service.
 *
 * The listener forwards both add and update events to BondHistoricalDataService,
 * which then calls its configured connector to append into allinquiries.txt.
 *
 * @author Hao Wang
 */

#ifndef BOND_INQUIRY_HISTORICAL_LISTENER_HPP
#define BOND_INQUIRY_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/inquiryservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include "BondHistoricalDataService.hpp"

 /**
  * BondInquiryHistoricalListener
  * Persists inquiry lifecycle events (RECEIVED/QUOTED/DONE/REJECTED) for auditing.
  */
class BondInquiryHistoricalListener : public ServiceListener< Inquiry<Bond> >
{
public:
    /**
     * @param hs Historical service that persists Inquiry<Bond> snapshots.
     */
    explicit BondInquiryHistoricalListener(BondHistoricalDataService< Inquiry<Bond> >* hs)
        : hist(hs)
    {
    }

    /**
     * Persist the inquiry when it is first seen.
     */
    void ProcessAdd(Inquiry<Bond>& i) override
    {
        // Persist keyed by inquiry id to keep the latest snapshot per inquiry.
        hist->PersistData(i.GetInquiryId(), i);
    }

    /**
     * Persist the inquiry when it is updated (e.g., QUOTED/DONE).
     */
    void ProcessUpdate(Inquiry<Bond>& i) override
    {
        hist->PersistData(i.GetInquiryId(), i);
    }

    void ProcessRemove(Inquiry<Bond>&) override {}

private:
    // Historical sink service (owned/managed elsewhere; listener only holds pointer).
    BondHistoricalDataService< Inquiry<Bond> >* hist;
};

#endif
