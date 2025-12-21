// ====================== BondExecutionConnector.hpp ======================
#ifndef BOND_EXECUTION_CONNECTOR_HPP
#define BOND_EXECUTION_CONNECTOR_HPP

#include "../base/soa.hpp"
#include "../products/TreasuryProducts.hpp"
#include "../base/executionservice.hpp"

#include <sys/socket.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <iostream>

class BondExecutionConnector : public Connector< ExecutionOrder<Bond> >
{
public:
    BondExecutionConnector(int port);

    virtual void Publish(ExecutionOrder<Bond>& data) override;

private:
    int port;
};

#endif
