/**
 * BondPricingConnector.hpp
 * Socket connector for feeding pricing updates into BondPricingService.
 *
 * Incoming message format (one line per update):
 *   CUSIP,FRAC_MID,FRAC_SPREAD\n
 *
 * FRAC uses US Treasury fractional notation, e.g. "100-25+".
 *
 * @author Hao Wang
 */
#ifndef BOND_PRICING_CONNECTOR_HPP
#define BOND_PRICING_CONNECTOR_HPP

#include "BondPricingService.hpp"
#include "../base/soa.hpp"

 /**
  * BondPricingConnector
  * Subscriber connector that listens on a TCP port and pushes price updates
  * into BondPricingService via UpdatePrice().
  */
class BondPricingConnector : public Connector< Price<Bond> >
{
public:
    /**
     * Construct a connector bound to a service instance and a TCP listening port.
     *
     * @param service_ Target service to receive parsed price updates.
     * @param port_    TCP port to listen on.
     */
    BondPricingConnector(BondPricingService* service_, int port_);

    /**
     * Publish price out (not used here).
     * This connector is subscriber-only for the project spec.
     */
    virtual void Publish(Price<Bond>& /*data*/) override {}

    /**
     * Start the socket listening loop (blocking).
     * Accepts a client and keeps reading newline-delimited messages until the client disconnects.
     */
    void Start();

private:
    BondPricingService* service;
    int port;
};

#endif
