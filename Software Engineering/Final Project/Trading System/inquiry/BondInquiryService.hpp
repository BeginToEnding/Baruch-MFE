/**
 * BondInquiryService.hpp
 * Inquiry service implementation for Treasuries.
 *
 * - Stores inquiries keyed by inquiry id.
 * - Notifies listeners on new/update.
 * - SendQuote / RejectInquiry publish through an outbound connector.
 *
 * @author Hao Wang
 */

#ifndef BOND_INQUIRY_SERVICE_HPP
#define BOND_INQUIRY_SERVICE_HPP

#include "../products/TreasuryProducts.hpp"
#include "../utils/ProductLookup.hpp"
#include "../base/inquiryservice.hpp"
#include "../base/soa.hpp"

#include <map>
#include <vector>
#include <string>

using namespace std;

/**
 * BondInquiryService
 * Manages inquiry lifecycle for Bond products.
 */
class BondInquiryService : public InquiryService<Bond>
{
public:
    /**
     * Construct the inquiry service.
     */
    BondInquiryService();

    /**
     * Retrieve an inquiry by inquiry id.
     */
    virtual Inquiry<Bond>& GetData(string key) override;

    /**
     * Receive new/updated inquiry objects (from connector or internal loopback).
     */
    virtual void OnMessage(Inquiry<Bond>& data) override;

    /**
     * Listener management.
     */
    virtual void AddListener(ServiceListener< Inquiry<Bond> >* listener) override;

    virtual const vector<ServiceListener< Inquiry<Bond> >*>&
        GetListeners() const override;

    /**
     * Quote an inquiry at the given price (decimal internally).
     * Connector will publish QUOTED and DONE states back.
     */
    virtual void SendQuote(const string& inquiryId, double price);

    /**
     * Reject an inquiry.
     */
    virtual void RejectInquiry(const string& inquiryId);

    /**
     * Set outbound connector (used by SendQuote/RejectInquiry).
     */
    void SetConnector(Connector< Inquiry<Bond> >* c);

private:
    // Inquiry id -> inquiry object
    map<string, Inquiry<Bond> > inquiries;

    // Downstream listeners (e.g., auto-quoter, historical)
    vector<ServiceListener< Inquiry<Bond> >*> listeners;

    // Outbound connector to publish inquiry responses
    Connector< Inquiry<Bond> >* connector;
};

#endif
