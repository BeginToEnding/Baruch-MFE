// ====================== BondMarketDataConnector.hpp ======================
#ifndef BOND_MARKET_DATA_CONNECTOR_HPP
#define BOND_MARKET_DATA_CONNECTOR_HPP

#include "BondMarketDataService.hpp"
#include <string>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>

class BondMarketDataConnector : public Connector< OrderBook<Bond> >
{
public:
    BondMarketDataConnector(BondMarketDataService* s, int port);

    virtual void Publish(OrderBook<Bond>& data) override {}

    void Start();

private:
    BondMarketDataService* service;
    int port;
};

#endif
