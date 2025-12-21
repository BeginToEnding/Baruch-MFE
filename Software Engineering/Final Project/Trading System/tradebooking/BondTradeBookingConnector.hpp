// ====================== BondTradeBookingConnector.hpp ======================
#ifndef BOND_TRADE_BOOKING_CONNECTOR_HPP
#define BOND_TRADE_BOOKING_CONNECTOR_HPP

#include "BondTradeBookingService.hpp"
#include <string>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>

class BondTradeBookingConnector : public Connector< Trade<Bond> >
{
public:
    BondTradeBookingConnector(BondTradeBookingService* service_, int port);

    // Publish is unused; inbound connector only
    virtual void Publish(Trade<Bond>& data) override {}

    void Start();

private:
    BondTradeBookingService* service;
    int port;
};

#endif
