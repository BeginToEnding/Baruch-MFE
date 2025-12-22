/**
 * BondTradeBookingConnector.hpp
 * Socket connector for feeding trades into BondTradeBookingService.
 *
 * Incoming message format (one line per trade):
 *   CUSIP,SIDE,QTY,FRAC_PRICE,TRADE_ID\n
 *
 * Note: price is in US Treasury fractional notation (1/256 ticks).
 *
 * @author Hao Wang
 */
#ifndef BOND_TRADE_BOOKING_CONNECTOR_HPP
#define BOND_TRADE_BOOKING_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "BondTradeBookingService.hpp"

#include <string>

 /**
  * BondTradeBookingConnector
  * Subscriber-only connector. It listens on a TCP port and pushes trades into the service.
  */
class BondTradeBookingConnector : public Connector< Trade<Bond> >
{
public:
    /**
     * Construct a connector bound to a service instance and a TCP listening port.
     */
    BondTradeBookingConnector(BondTradeBookingService* service_, int port_);

    /**
     * Publish is unused here (inbound connector only).
     */
    virtual void Publish(Trade<Bond>& /*data*/) override {}

    /**
     * Start the socket listening loop (blocking).
     */
    void Start();

private:
    BondTradeBookingService* service;
    int port;
};

#endif
