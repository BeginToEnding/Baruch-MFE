/**
 * BondExecutionConnector.hpp
 * Outbound connector that publishes ExecutionOrder<Bond> via TCP socket.
 *
 * Message format (newline-delimited):
 *   EXEC,cusip,orderId,price,qty\n
 *
 * @author Hao Wang
 */

#ifndef BOND_EXECUTION_CONNECTOR_HPP
#define BOND_EXECUTION_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../base/executionservice.hpp"
#include "../products/TreasuryProducts.hpp"

#include <iostream>

using namespace std;

/**
 * BondExecutionConnector
 * Pushes executions to an external process listening on localhost:port.
 */
class BondExecutionConnector : public Connector< ExecutionOrder<Bond> >
{
public:
    /**
     * Construct the outbound connector.
     *
     * @param port_ TCP port on localhost where subscriber listens.
     */
    BondExecutionConnector(int port_);

    /**
     * Publish one execution order via TCP.
     */
    virtual void Publish(ExecutionOrder<Bond>& data) override;

private:
    int port;
};

#endif
