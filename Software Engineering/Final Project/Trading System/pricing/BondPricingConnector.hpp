// ====================== BondPricingConnector.hpp ======================
#ifndef BOND_PRICING_CONNECTOR_HPP
#define BOND_PRICING_CONNECTOR_HPP

#include "BondPricingService.hpp"
#include <string>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>

class BondPricingConnector : public Connector< Price<Bond> >
{
public:
    BondPricingConnector(BondPricingService* service_, int port);

    // Publish price out (not used here)
    virtual void Publish(Price<Bond>& data) override {}

    // Start socket listening loop
    void Start();

private:
    BondPricingService* service;
    int port;
};

#endif
