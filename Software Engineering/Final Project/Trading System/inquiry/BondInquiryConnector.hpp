// ====================== BondInquiryConnector.hpp ======================
#ifndef BOND_INQUIRY_CONNECTOR_HPP
#define BOND_INQUIRY_CONNECTOR_HPP

#include "BondInquiryService.hpp"
#include <string>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sstream>

class BondInquiryConnector : public Connector< Inquiry<Bond> >
{
public:
    BondInquiryConnector(BondInquiryService* service_, int port);

    // Service calls this when sending quote/reject
    virtual void Publish(Inquiry<Bond>& data) override;

    // External process sends RECEIVED inquiry
    void Start();

private:
    BondInquiryService* service;
    int port;
};

#endif
