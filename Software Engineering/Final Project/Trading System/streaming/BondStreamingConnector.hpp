/**
 * BondStreamingConnector.hpp
 * Outbound connector that publishes PriceStream<Bond> via TCP socket.
 *
 * Message format (newline-delimited):
 *   STREAM,cusip,bidPx,askPx,bidQty,askQty\n
 *
 * NOTE:
 * - Internal computations use decimal prices.
 * - If your subscriber expects fractional, convert before sending.
 *
 * @author Hao Wang
 */

#ifndef BOND_STREAMING_CONNECTOR_HPP
#define BOND_STREAMING_CONNECTOR_HPP

#include "../base/streamingservice.hpp"
#include "../products/TreasuryProducts.hpp"

#include <sstream>

using namespace std;

/**
 * BondStreamingConnector
 * Publishes streams to localhost:port for an external process to print/consume.
 */
class BondStreamingConnector : public Connector< PriceStream<Bond> >
{
public:
    /**
     * @param port_ TCP port on localhost where subscriber listens.
     */
    BondStreamingConnector(int port_);

    /**
     * Publish stream via TCP socket.
     */
    virtual void Publish(PriceStream<Bond>& data) override;

private:
    int port;
};

#endif
