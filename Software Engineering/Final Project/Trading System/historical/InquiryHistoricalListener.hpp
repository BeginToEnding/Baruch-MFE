#ifndef BOND_INQUIRY_HISTORICAL_LISTENER_HPP
#define BOND_INQUIRY_HISTORICAL_LISTENER_HPP

#include "../base/soa.hpp"
#include "../base/inquiryservice.hpp"
#include "BondHistoricalDataService.hpp"

class BondInquiryHistoricalListener : public ServiceListener< Inquiry<Bond> >
{
public:
    explicit BondInquiryHistoricalListener(BondHistoricalDataService<Inquiry<Bond>>* hs)
        : hist(hs) {}

    void ProcessAdd(Inquiry<Bond>& i) override { hist->PersistData(i.GetInquiryId(), i); }
    void ProcessUpdate(Inquiry<Bond>& i) override { hist->PersistData(i.GetInquiryId(), i); }
    void ProcessRemove(Inquiry<Bond>&) override {}

private:
    BondHistoricalDataService<Inquiry<Bond>>* hist;
};

#endif
