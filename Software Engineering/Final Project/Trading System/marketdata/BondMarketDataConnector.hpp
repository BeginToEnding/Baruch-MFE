/**
 * BondMarketDataConnector.hpp
 * Inbound connector for BondMarketDataService.
 *
 * This connector listens on a TCP port and receives streamed market data lines:
 *   cusip,mid,topSpread\n
 *
 * mid and topSpread are in Treasury fractional notation when sent from feeder,
 * and are converted to decimal internally using FractionalToDecimal().
 *
 * @author Hao Wang
 */

#ifndef BOND_MARKET_DATA_CONNECTOR_HPP
#define BOND_MARKET_DATA_CONNECTOR_HPP

#include "BondMarketDataService.hpp"

#include <string>


using namespace std;

/**
 * BondMarketDataConnector
 * Listens on a TCP socket and pushes parsed updates into BondMarketDataService.
 */
class BondMarketDataConnector : public Connector< OrderBook<Bond> >
{
public:
    /**
     * Construct an inbound connector.
     *
     * @param s    target BondMarketDataService
     * @param port listening TCP port
     */
    BondMarketDataConnector(BondMarketDataService* s, int port);

    /**
     * Outbound publish is not used for market data in this project.
     */
    virtual void Publish(OrderBook<Bond>& /*data*/) override {}

    /**
     * Blocking socket loop: accept clients and read newline-delimited updates.
     */
    void Start();

private:
    BondMarketDataService* service;
    int port;
};

#endif
