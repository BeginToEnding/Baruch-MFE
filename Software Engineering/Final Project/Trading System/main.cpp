/**
 * main.cpp
 * Entry point of the Bond trading system.
 *
 * The system follows an SOA publish/subscribe architecture:
 *   - External feeder processes publish file data into inbound connectors via TCP sockets
 *   - Inbound connectors parse lines and push objects into services
 *   - Services notify listeners to drive the full workflow:
 *       Pricing -> AlgoStreaming -> Streaming -> Publish to external
 *       MarketData -> AlgoExecution -> Execution -> TradeBooking -> Position -> Risk
 *       Inquiry -> AutoQuote -> Publish QUOTED/DONE -> back into InquiryService
 *   - Historical services persist snapshots back to text files
 *
 * @author Hao Wang
 */

#include <thread>
#include <iostream>

 // base
#include "base/soa.hpp"

// products & utils
#include "products/TreasuryProducts.hpp"
#include "utils/TimeUtils.hpp"
#include "utils/PriceUtils.hpp"

// pricing
#include "pricing/BondPricingService.hpp"
#include "pricing/BondPricingConnector.hpp"

// market data
#include "marketdata/BondMarketDataService.hpp"
#include "marketdata/BondMarketDataConnector.hpp"

// trade booking
#include "tradebooking/BondTradeBookingService.hpp"
#include "tradebooking/BondTradeBookingConnector.hpp"
#include "tradebooking/BondTradeToPositionListener.hpp"

// position & risk
#include "risk/BondPositionService.hpp"
#include "risk/BondRiskService.hpp"
#include "risk/BondPositionToRiskListener.hpp"

// execution
#include "execution/BondAlgoExecutionService.hpp"
#include "execution/BondExecutionService.hpp"
#include "execution/BondExecutionConnector.hpp"
#include "execution/BondAlgoExecutionListener.hpp"
#include "execution/BondAlgoExecutionToExecutionListener.hpp"
#include "execution/BondExecutionToTradeListener.hpp"

// streaming
#include "streaming/BondAlgoStreamingService.hpp"
#include "streaming/BondStreamingService.hpp"
#include "streaming/BondStreamingConnector.hpp"
#include "streaming/BondAlgoStreamingListener.hpp"
#include "streaming/BondAlgoStreamingToStreamingListener.hpp"

// inquiry
#include "inquiry/BondInquiryService.hpp"
#include "inquiry/BondInquiryConnector.hpp"
#include "inquiry/BondInquiryListener.hpp"

// historical
#include "historical/BondHistoricalDataService.hpp"
#include "historical/BondPositionHistoricalConnector.hpp"
#include "historical/BondPositionHistoricalListener.hpp"
#include "historical/BondRiskHistoricalConnector.hpp"
#include "historical/BondRiskHistoricalListener.hpp"
#include "historical/BondExecutionHistoricalConnector.hpp"
#include "historical/BondExecutionHistoricalListener.hpp"
#include "historical/BondStreamingHistoricalConnector.hpp"
#include "historical/BondStreamingHistoricalListener.hpp"
#include "historical/BondInquiryHistoricalConnector.hpp"
#include "historical/BondInquiryHistoricalListener.hpp"

// GUI
#include "gui/GUIService.hpp"
#include "gui/GUIThrottleListener.hpp"

int main()
{
    // ---------------------------
    // 1) Create core services
    // ---------------------------
    BondPricingService* pricingService = new BondPricingService();
    BondMarketDataService* marketDataService = new BondMarketDataService();
    BondTradeBookingService* tradeBookingService = new BondTradeBookingService();
    BondPositionService* positionService = new BondPositionService();
    BondRiskService* riskService = new BondRiskService();

    BondAlgoExecutionService* algoExecutionService = new BondAlgoExecutionService();
    BondExecutionService* executionService = new BondExecutionService();

    BondAlgoStreamingService* algoStreamingService = new BondAlgoStreamingService();
    BondStreamingService* streamingService = new BondStreamingService();

    BondInquiryService* inquiryService = new BondInquiryService();

    GUIService* guiService = new GUIService();

    // ---------------------------
    // 2) Outbound connectors (system publishes out)
    // ---------------------------
    // ExecutionService publishes executions to an external process listening on port 8001.
    BondExecutionConnector* execPubConnector = new BondExecutionConnector(8001);
    executionService->SetConnector(execPubConnector);

    // StreamingService publishes streaming prices to an external process listening on port 8002.
    BondStreamingConnector* streamPubConnector = new BondStreamingConnector(8002);
    streamingService->SetConnector(streamPubConnector);

    // ---------------------------
    // 3) Historical services + connectors (persist to files)
    // ---------------------------
    BondHistoricalDataService< Position<Bond> >* posHistSvc = new BondHistoricalDataService< Position<Bond> >();
    posHistSvc->SetConnector(new BondPositionHistoricalConnector("positions.txt"));

    BondHistoricalDataService<RiskLine>* riskHistSvc = new BondHistoricalDataService<RiskLine>();
    riskHistSvc->SetConnector(new BondRiskHistoricalConnector("risk.txt"));

    BondHistoricalDataService< ExecutionOrder<Bond> >* execHistSvc = new BondHistoricalDataService< ExecutionOrder<Bond> >();
    execHistSvc->SetConnector(new BondExecutionHistoricalConnector("executions.txt"));

    BondHistoricalDataService< PriceStream<Bond> >* streamHistSvc = new BondHistoricalDataService< PriceStream<Bond> >();
    streamHistSvc->SetConnector(new BondStreamingHistoricalConnector("streaming.txt"));

    BondHistoricalDataService< Inquiry<Bond> >* inqHistSvc = new BondHistoricalDataService< Inquiry<Bond> >();
    inqHistSvc->SetConnector(new BondInquiryHistoricalConnector("allinquiries.txt"));

    // ---------------------------
    // 4) Inbound connectors (external processes publish in)
    // ---------------------------
    // These connectors are TCP servers listening for feeder publishers.
    BondPricingConnector* pricingConn = new BondPricingConnector(pricingService, 9001);
    BondMarketDataConnector* marketDataConn = new BondMarketDataConnector(marketDataService, 9002);
    BondTradeBookingConnector* tradeConn = new BondTradeBookingConnector(tradeBookingService, 9003);
    BondInquiryConnector* inquiryConn = new BondInquiryConnector(inquiryService, 9004);

    // Inquiry is bidirectional: service needs connector to Publish QUOTED/DONE updates.
    inquiryService->SetConnector(inquiryConn);

    // ---------------------------
    // 5) Wire listeners (MUST be done BEFORE starting connector threads)
    // ---------------------------

    // Pricing -> AlgoStreaming -> Streaming -> outbound publish
    pricingService->AddListener(new BondAlgoStreamingListener(algoStreamingService));
    algoStreamingService->AddListener(new BondAlgoStreamingToStreamingListener(streamingService));

    // Pricing -> GUI (throttled by 300ms; log only first 100 updates)
    pricingService->AddListener(new GUIThrottleListener(guiService));

    // MarketData -> AlgoExecution -> ExecutionService -> TradeBooking
    marketDataService->AddListener(new BondAlgoExecutionListener(algoExecutionService));
    algoExecutionService->AddListener(new BondAlgoExecutionToExecutionListener(executionService));
    executionService->AddListener(new BondExecutionToTradeListener(tradeBookingService));

    // TradeBooking -> Position -> Risk
    tradeBookingService->AddListener(new BondTradeToPositionListener(positionService));
    positionService->AddListener(new BondPositionToRiskListener(riskService));

    // Inquiry auto-quote: RECEIVED -> SendQuote(100)
    inquiryService->AddListener(new BondInquiryListener(inquiryService));

    // ---------------------------
    // 6) Historical listeners (persist snapshots)
    // ---------------------------
    positionService->AddListener(new BondPositionHistoricalListener(posHistSvc));
    riskService->AddListener(new BondRiskHistoricalListener(riskHistSvc, riskService));
    executionService->AddListener(new BondExecutionHistoricalListener(execHistSvc));
    streamingService->AddListener(new BondStreamingHistoricalListener(streamHistSvc));
    inquiryService->AddListener(new BondInquiryHistoricalListener(inqHistSvc));

    // ---------------------------
    // 7) Start inbound connector threads
    // ---------------------------
    // Each Start() call blocks forever, so each connector runs on its own thread.
    std::thread t1(&BondPricingConnector::Start, pricingConn);
    std::thread t2(&BondMarketDataConnector::Start, marketDataConn);
    std::thread t3(&BondTradeBookingConnector::Start, tradeConn);
    std::thread t4(&BondInquiryConnector::Start, inquiryConn);

    // Join threads (main blocks forever under normal operation).
    t1.join();
    t2.join();
    t3.join();
    t4.join();

    return 0;
}
