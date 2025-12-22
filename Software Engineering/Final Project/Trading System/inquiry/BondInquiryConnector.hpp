/**
 * BondInquiryConnector.hpp
 * Inbound/outbound connector for Inquiry<Bond>.
 *
 * - Start(): listens on a TCP port and receives inquiry messages (from feeder/external).
 * - Publish(): used by BondInquiryService to send QUOTED and DONE messages back
 *   into the system (loopback to the same listening port).
 *
 * Message format (newline-delimited):
 *   id,cusip,side,qty,pxFrac[,STATE]\n
 *
 * Price is in Treasury fractional notation in the wire/file message.
 * Internally, we convert to decimal for calculations.
 *
 * @author Hao Wang
 */

#ifndef BOND_INQUIRY_CONNECTOR_HPP
#define BOND_INQUIRY_CONNECTOR_HPP

#include "BondInquiryService.hpp"
#include <string>
#include <sstream>

using namespace std;

/**
 * BondInquiryConnector
 * Handles socket IO for inquiry messages.
 */
class BondInquiryConnector : public Connector< Inquiry<Bond> >
{
public:
    /**
     * @param service_ Target inquiry service to receive parsed Inquiry objects.
     * @param port     Listening port.
     */
    BondInquiryConnector(BondInquiryService* service_, int port);

    /**
     * Service calls this when sending quote/reject.
     * In this project we publish QUOTED then DONE back into the same port.
     */
    virtual void Publish(Inquiry<Bond>& data) override;

    /**
     * Start socket listening loop for incoming inquiry messages.
     */
    void Start();

private:
    BondInquiryService* service;
    int port;
};

#endif
