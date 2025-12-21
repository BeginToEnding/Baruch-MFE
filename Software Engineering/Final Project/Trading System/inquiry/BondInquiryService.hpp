// ====================== BondInquiryService.hpp ======================
#ifndef BOND_INQUIRY_SERVICE_HPP
#define BOND_INQUIRY_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/inquiryservice.hpp"
#include "../base/soa.hpp"
#include <map>
#include <vector>

class BondInquiryService : public InquiryService<Bond>
{
public:
    BondInquiryService();

    // Retrieve existing inquiry
    virtual Inquiry<Bond>& GetData(string key) override;

    // Receive new/updated inquiry
    virtual void OnMessage(Inquiry<Bond>& data) override;

    // Listener management
    virtual void AddListener(ServiceListener< Inquiry<Bond> >* listener) override;
    virtual const vector<ServiceListener< Inquiry<Bond> >*>&
        GetListeners() const override;

    // QUOTE / REJECT APIs
    virtual void SendQuote(const string& inquiryId, double price);
    virtual void RejectInquiry(const string& inquiryId);

    void SetConnector(Connector< Inquiry<Bond> >* c);

private:
    map<string, Inquiry<Bond>> inquiries;
    vector<ServiceListener< Inquiry<Bond> >*> listeners;
    Connector< Inquiry<Bond> >* connector;
};

#endif
