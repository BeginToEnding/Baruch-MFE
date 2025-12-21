// ====================== BondStreamingConnector.hpp ======================
#ifndef BOND_STREAMING_CONNECTOR_HPP
#define BOND_STREAMING_CONNECTOR_HPP

#include "../base/streamingservice.hpp"
#include "../products/TreasuryProducts.hpp"
#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <sstream>

class BondStreamingConnector : public Connector< PriceStream<Bond> >
{
public:
    BondStreamingConnector(int port);

    virtual void Publish(PriceStream<Bond>& data) override;

private:
    int port;
};

#endif
