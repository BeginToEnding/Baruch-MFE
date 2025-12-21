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
#include "pricing/BondPricingListener.hpp"

// market data
#include "marketdata/BondMarketDataService.hpp"
#include "marketdata/BondMarketDataConnector.hpp"
#include "marketdata/BondMarketDataListener.hpp"

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
#include "historical/PositionHistoricalConnector.hpp"
#include "historical/PositionHistoricalListener.hpp"
#include "historical/RiskHistoricalConnector.hpp"
#include "historical/RiskHistoricalListener.hpp"
#include "historical/ExecutionHistoricalConnector.hpp"
#include "historical/ExecutionHistoricalListener.hpp"
#include "historical/StreamingHistoricalConnector.hpp"
#include "historical/StreamingHistoricalListener.hpp"
#include "historical/InquiryHistoricalConnector.hpp"
#include "historical/InquiryHistoricalListener.hpp"

// GUI
#include "gui/GUIService.hpp"
#include "gui/GUIThrottleListener.hpp"

int main()
{
    // ---------------------------
    // Create Services
    // ---------------------------
    auto* pricingService = new BondPricingService();
    auto* marketDataService = new BondMarketDataService();
    auto* tradeBookingService = new BondTradeBookingService();
    auto* positionService = new BondPositionService();
    auto* riskService = new BondRiskService();
    auto* algoExecutionService = new BondAlgoExecutionService();
    auto* executionService = new BondExecutionService();
    auto* algoStreamingService = new BondAlgoStreamingService();
    auto* streamingService = new BondStreamingService();
    auto* inquiryService = new BondInquiryService();
    auto* guiService = new GUIService();

    // ---------------------------
    // Outbound connectors
    // ---------------------------
    auto* execPubConnector = new BondExecutionConnector(8001);
    executionService->SetConnector(execPubConnector);

    auto* streamPubConnector = new BondStreamingConnector(8002);
    streamingService->SetConnector(streamPubConnector);

    // ---------------------------
    // Historical services + connectors
    // ---------------------------
    auto* posHistSvc = new BondHistoricalDataService< Position<Bond> >();
    posHistSvc->SetConnector(new BondPositionHistoricalConnector("positions.txt"));

    // Risk (single connector, merged SECURITY+BUCKET)
    auto* riskHistSvc = new BondHistoricalDataService<RiskLine>();
    riskHistSvc->SetConnector(new BondRiskHistoricalConnector("risk.txt"));

    auto* execHistSvc = new BondHistoricalDataService< ExecutionOrder<Bond> >();
    execHistSvc->SetConnector(new BondExecutionHistoricalConnector("executions.txt"));

    auto* streamHistSvc = new BondHistoricalDataService< PriceStream<Bond> >();
    streamHistSvc->SetConnector(new BondStreamingHistoricalConnector("streaming.txt"));

    auto* inqHistSvc = new BondHistoricalDataService< Inquiry<Bond> >();
    inqHistSvc->SetConnector(new BondInquiryHistoricalConnector("allinquiries.txt"));

    // ---------------------------
    // Inbound connectors (subscriber)
    // ---------------------------
    auto* pricingConn = new BondPricingConnector(pricingService, 9001);
    auto* marketDataConn = new BondMarketDataConnector(marketDataService, 9002);
    auto* tradeConn = new BondTradeBookingConnector(tradeBookingService, 9003);
    auto* inquiryConn = new BondInquiryConnector(inquiryService, 9004);

    // Inquiry is bidirectional; allow service to Publish quotes
    inquiryService->SetConnector(inquiryConn);

    // ---------------------------
    // Wiring listeners (do this BEFORE starting threads)
    // ---------------------------

    // Pricing ¡ú AlgoStreaming
    pricingService->AddListener(new BondAlgoStreamingListener(algoStreamingService));

    // AlgoStreaming ¡ú StreamingService
    algoStreamingService->AddListener(new BondAlgoStreamingToStreamingListener(streamingService));

    // Pricing ¡ú GUI
    pricingService->AddListener(new GUIThrottleListener(guiService));

    // MarketData ¡ú AlgoExecution
    marketDataService->AddListener(new BondAlgoExecutionListener(algoExecutionService));

    // AlgoExecution ¡ú ExecutionService
    algoExecutionService->AddListener(new BondAlgoExecutionToExecutionListener(executionService));

    // ExecutionService ¡ú TradeBookingService
    executionService->AddListener(new BondExecutionToTradeListener(tradeBookingService));

    // TradeBooking ¡ú Position
    tradeBookingService->AddListener(new BondTradeToPositionListener(positionService));

    // Position ¡ú Risk
    positionService->AddListener(new BondPositionToRiskListener(riskService));

    // Inquiry auto-quote
    inquiryService->AddListener(new BondInquiryListener(inquiryService));

    // ---------------------------
    // Historical listeners
    // ---------------------------
    positionService->AddListener(new BondPositionHistoricalListener(posHistSvc));
    riskService->AddListener(new BondRiskHistoricalListener(riskHistSvc, riskService));
    executionService->AddListener(new BondExecutionHistoricalListener(execHistSvc));
    streamingService->AddListener(new BondStreamingHistoricalListener(streamHistSvc));
    inquiryService->AddListener(new BondInquiryHistoricalListener(inqHistSvc));

    // ---------------------------
    // Start threads (after wiring)
    // ---------------------------
    std::thread t1(&BondPricingConnector::Start, pricingConn);
    std::thread t2(&BondMarketDataConnector::Start, marketDataConn);
    std::thread t3(&BondTradeBookingConnector::Start, tradeConn);
    std::thread t4(&BondInquiryConnector::Start, inquiryConn);

    t1.join();
    t2.join();
    t3.join();
    t4.join();
    return 0;
}
