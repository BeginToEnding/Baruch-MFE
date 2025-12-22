# US Treasury Trading System (SOA / Publish-Subscribe)

This repository implements a simplified US Treasury trading system using a **Service / Listener / Connector** architecture.
External processes feed text files into the system via sockets. The system transforms and routes data through services and listeners, publishes executions/streams outward via sockets, and persists historical outputs to files.

**Author:** Hao Wang

---

## 1. Directory Layout (What you see in the repo)

src/
  base/        # Course-provided interfaces & core types (do not modify)
  products/    # Treasury universe definition
  utils/       # Shared utilities (time, price conversion, book cycle, lookup)
  pricing/     # Pricing service + inbound pricing connector
  marketdata/  # Market data service + inbound market data connector
  tradebooking/ # Trade booking service + inbound trade connector + trade->position listener
  risk/        # Position service, risk service, position->risk listener
  execution/   # Algo execution, execution service, outbound execution connector, listeners
  streaming/   # Algo streaming, streaming service, outbound stream connector, listeners
  inquiry/     # Inquiry service + bidirectional inquiry connector + auto-quote listener
  historical/  # Historical data services + connectors/listeners that persist to files
  gui/         # GUI throttled sink writing gui.txt

FileFeeder.cpp  # External feeder process: reads a file and pushes lines to a socket port

GenerateSmapleData.cpp # Generate sample input files (prices, market data, trades, inquiries) for the US Treasury trading system.

main.cpp          # System bootstrap: creates services, wires listeners/connectors, starts socket threads

---

## 2. Core Architecture (Service / Listener / Connector)

### 2.1 Service

A **Service** owns in-memory state keyed by an identifier (CUSIP / tradeId / orderId / inquiryId).
It receives new data via `OnMessage(...)` (or a convenience wrapper like `UpdatePrice(...)`), stores it, and notifies subscribers.

Examples:
- `BondPricingService`: stores `Price<Bond>` keyed by **CUSIP**
- `BondMarketDataService`: stores `OrderBook<Bond>` keyed by **CUSIP**
- `BondTradeBookingService`: stores `Trade<Bond>` keyed by **tradeId**
- `BondPositionService`: stores `Position<Bond>` keyed by **CUSIP**
- `BondRiskService`: stores `PV01<Bond>` keyed by **CUSIP**
- `BondExecutionService`: stores `ExecutionOrder<Bond>` keyed by **orderId**
- `BondStreamingService`: stores `PriceStream<Bond>` keyed by **CUSIP**
- `BondInquiryService`: stores `Inquiry<Bond>` keyed by **inquiryId**

### 2.2 ServiceListener

A **ServiceListener** is the publish/subscribe glue. It reacts to:
- `ProcessAdd(...)`
- `ProcessUpdate(...)`
- `ProcessRemove(...)`

Listeners allow modules to communicate **without direct references between services** (decoupling).

### 2.3 Connector

A **Connector** bridges external I/O:
- **Inbound connectors**: socket servers; parse text lines; convert fractional prices; call service methods.
- **Outbound connectors**: take internal objects; serialize to text; send to an external socket receiver.
- **Historical connectors**: take internal objects; serialize to text; append to a file.

## 3. Price Format Rule (Important)

**All file I/O uses US Treasury fractional notation with smallest tick 1/256.**
Internal calculations use decimal doubles.

Conversion is centralized in:
- `utils/PriceUtils.hpp`
  - `FractionalToDecimal(...)` on inbound parsing
  - `DecimalToFractional(...)` on historical/GUI output

Example: `100-25+` means `100 + 25/32 + 4/256`.

## 4. Module Breakdown (What files exist and what they do)

### 4.1 `products/`
- `TreasuryProducts.hpp / TreasuryProducts.cpp`
  - Defines `Treasury : public Bond`
  - Defines the 7-security universe
  - Provides lookup: `TreasuryUniverse()`, `GetBond(cusip)`, `GetBondByTicker(ticker)`

### 4.2 `utils/`
- `PriceUtils.hpp`
  - Fractional <-> decimal conversion (1/256 ticks)
- `TimeUtils.hpp`
  - `NowTimestampMS()` timestamp with millisecond precision
- `Books.hpp`
  - Book constants and `NextBook(int& idx)` round-robin helper
- `ProductLookup.hpp`
  - Convenience wrapper around treasury universe lookup

### 4.3 `pricing/`
- `BondPricingConnector.hpp / BondPricingConnector.cpp`
  - **Inbound** socket server on port **9001**
  - Parses: `CUSIP,MidFrac,SpreadFrac`
  - Converts to decimal and calls `BondPricingService::UpdatePrice(...)`
- `BondPricingService.hpp / BondPricingService.cpp`
  - Stores `Price<Bond>` keyed by CUSIP
  - Notifies listeners (AlgoStreaming, GUI)
- `BondPricingListener.hpp`
  - Placeholder listener (not required for main dataflow)

### 4.4 `marketdata/`
- `BondMarketDataConnector.hpp / BondMarketDataConnector.cpp`
  - **Inbound** socket server on port **9002**
  - Parses: `CUSIP,MidFrac,TopSpreadFrac`
  - Converts to decimal and calls `BondMarketDataService::BuildAndSendOrderBook(...)`
- `BondMarketDataService.hpp / BondMarketDataService.cpp`
  - Builds a 5x5 order book (5 bid + 5 offer levels)
  - Stores `OrderBook<Bond>` and `BestBidOffer`
  - Notifies listeners (AlgoExecution)
- `BondMarketDataListener.hpp`
  - Placeholder listener (not required for main dataflow)

### 4.5 `tradebooking/`
- `BondTradeBookingConnector.hpp / BondTradeBookingConnector.cpp`
  - **Inbound** socket server on port **9003**
  - Parses: `CUSIP,SIDE,QTY,PXFrac,TRADEID`
  - Converts to decimal and calls `BondTradeBookingService::BookTrade(...)`
- `BondTradeBookingService.hpp / BondTradeBookingService.cpp`
  - Stores `Trade<Bond>` keyed by tradeId
  - Notifies listeners
- `BondTradeToPositionListener.hpp`
  - Receives trades and calls `BondPositionService::AddTrade(...)`

### 4.6 `risk/`
- `BondPositionService.hpp / BondPositionService.cpp`
  - Maintains per-book positions and aggregate per CUSIP
  - Notifies listeners
- `BondPositionToRiskListener.hpp`
  - Receives positions and calls `BondRiskService::AddPosition(...)`
- `BondRiskService.hpp / BondRiskService.cpp`
  - Computes PV01 for each security using realistic PV01 values
  - Computes bucket risk:
    - FrontEnd = (2Y, 3Y)
    - Belly    = (5Y, 7Y, 10Y)
    - LongEnd  = (20Y, 30Y)

### 4.7 `execution/`
- `BondAlgoExecutionService.hpp / BondAlgoExecutionService.cpp`
  - Receives market data (OrderBook)
  - Aggresses top-of-book only when spread == 1/128
  - Alternates BUY/SELL and uses full top-of-book size
- `BondAlgoExecutionListener.hpp`
  - Subscribes to MarketDataService and calls algo `ProcessMarketData(...)`
- `BondAlgoExecutionToExecutionListener.hpp`
  - Forwards algo execution orders to ExecutionService
- `BondExecutionService.hpp / BondExecutionService.cpp`
  - Stores execution orders
  - Notifies listeners (Execution->Trade)
  - Publishes externally via `BondExecutionConnector` to port **8001**
- `BondExecutionConnector.hpp / BondExecutionConnector.cpp`
  - **Outbound**: sends `EXEC,cusip,orderId,px,qty\n` to port 8001
- `BondExecutionToTradeListener.hpp`
  - Converts executions into trades and sends them into TradeBookingService
  - Book is assigned in round-robin TRSY1->TRSY2->TRSY3

### 4.8 `streaming/`
- `BondAlgoStreamingService.hpp / BondAlgoStreamingService.cpp`
  - Receives pricing updates
  - Creates `PriceStream<Bond>` with:
    - visible alternating 1MM / 2MM
    - hidden = 2 * visible
- `BondAlgoStreamingListener.hpp`
  - Subscribes to PricingService and calls algo `ProcessPrice(...)`
- `BondAlgoStreamingToStreamingListener.hpp`
  - Forwards streams to StreamingService
- `BondStreamingService.hpp / BondStreamingService.cpp`
  - Stores streams
  - Publishes externally via `BondStreamingConnector` to port **8002**
- `BondStreamingConnector.hpp / BondStreamingConnector.cpp`
  - **Outbound**: sends `STREAM,cusip,bidPx,askPx,bidQty,askQty\n`

### 4.9 `inquiry/`
- `BondInquiryConnector.hpp / BondInquiryConnector.cpp`
  - **Inbound** socket server on port **9004**
  - Parses:
    - from file feeder: `inqId,cusip,side,qty,pxFrac`
    - from loopback publish: `inqId,cusip,side,qty,pxFrac,state`
  - Also acts as **outbound**: when InquiryService quotes, it sends QUOTED then DONE back into port 9004
- `BondInquiryService.hpp / BondInquiryService.cpp`
  - Stores inquiries keyed by inquiryId
  - `SendQuote(...)` triggers connector publish
- `BondInquiryListener.hpp`
  - Auto-quote: on RECEIVED, send quote price = 100.0

### 4.10 `historical/`
- `BondHistoricalDataService.hpp` (template)
  - Generic persister service for type `T`
  - `PersistData(key, obj)` stores snapshot and calls its connector `Publish(...)`

Position persistence:
- `PositionHistoricalListener.hpp` subscribes to PositionService
- `PositionHistoricalConnector.hpp` appends to `positions.txt`

Risk persistence:
- `RiskHistoricalListener.hpp` subscribes to RiskService
- `RiskHistoricalConnector.hpp` appends to `risk.txt` (SECURITY + BUCKET lines)

Execution persistence:
- `ExecutionHistoricalListener.hpp` subscribes to ExecutionService
- `ExecutionHistoricalConnector.hpp` appends to `executions.txt`

Streaming persistence:
- `StreamingHistoricalListener.hpp` subscribes to StreamingService
- `StreamingHistoricalConnector.hpp` appends to `streaming.txt`

Inquiry persistence:
- `InquiryHistoricalListener.hpp` subscribes to InquiryService
- `InquiryHistoricalConnector.hpp` appends to `allinquiries.txt`

All historical output prices (when applicable) are written using `DecimalToFractional(...)`.

### 4.11 `gui/`
- `GUIService.hpp / GUIService.cpp`
  - Sink: writes first 100 throttled pricing updates to `gui.txt`
  - Uses `NowTimestampMS()` and `DecimalToFractional(...)`
- `GUIThrottleListener.hpp`
  - 300ms throttle on updates from PricingService

## 5. Runtime Wiring (What main.cpp does)

`main.cpp` is the system bootstrap. It does:
1) Construct all services  
2) Construct outbound connectors (Execution->8001, Streaming->8002)  
3) Construct historical services/connectors  
4) Construct inbound connectors (Pricing->9001, MarketData->9002, Trades->9003, Inquiry->9004)  
5) Register all listeners (the dataflow graph)  
6) Start inbound connector threads; each thread runs forever in `Start()`.

## 6. Complete Dataflow (End-to-end)

### 6.1 Pricing -> Streaming + GUI

prices.txt -> FileFeeder -> (9001) BondPricingConnector
  -> BondPricingService
     -> BondAlgoStreamingListener -> BondAlgoStreamingService
        -> BondAlgoStreamingToStreamingListener -> BondStreamingService
           -> BondStreamingConnector -> (8002 external receiver)
           -> BondStreamingHistoricalListener -> streaming.txt
     -> GUIThrottleListener -> GUIService -> gui.txt

### 6.2 MarketData -> AlgoExecution -> Execution -> Trade -> Position -> Risk

marketdata.txt -> FileFeeder -> (9002) BondMarketDataConnector
  -> BondMarketDataService
     -> BondAlgoExecutionListener -> BondAlgoExecutionService
        (only when spread == 1/128, alternates aggress direction, uses full size)
        -> BondAlgoExecutionToExecutionListener -> BondExecutionService
           -> BondExecutionConnector -> (8001 external receiver)
           -> BondExecutionHistoricalListener -> executions.txt
           -> BondExecutionToTradeListener -> BondTradeBookingService
              -> BondTradeToPositionListener -> BondPositionService
                 -> BondPositionHistoricalListener -> positions.txt
                 -> BondPositionToRiskListener -> BondRiskService
                    -> BondRiskHistoricalListener -> risk.txt (SECURITY + BUCKET)

### 6.3 External Trades -> Position -> Risk

trades.txt -> FileFeeder -> (9003) BondTradeBookingConnector
  -> BondTradeBookingService -> Position -> Risk -> Historical files

inquiries.txt -> FileFeeder -> (9004) BondInquiryConnector
  -> BondInquiryService (RECEIVED)
     -> BondInquiryListener calls SendQuote(price=100)
        -> BondInquiryConnector.Publish sends QUOTED then DONE back to (9004)
           -> BondInquiryConnector receives those lines and calls BondInquiryService::OnMessage(...)
              -> BondInquiryHistoricalListener -> allinquiries.txt

---

## 7. Input/Output Files

### 7.1 Input files (fed by FileFeeder)
- `prices.txt`      -> port 9001
- `marketdata.txt`  -> port 9002
- `trades.txt`      -> port 9003
- `inquiries.txt`   -> port 9004

### 7.2 Output files (persisted by Historical/GUI)
- `positions.txt`
- `risk.txt`
- `executions.txt`
- `streaming.txt`
- `allinquiries.txt`
- `gui.txt`

## 8. How to Run

### 8.1 Start the trading system

Run the main executable first so ports are listening:
- 9001 pricing
- 9002 market data
- 9003 trades
- 9004 inquiries

### 8.2 Feed each file using the external feeder tool

Run each command in a separate terminal (or sequentially):

```bash
feeder prices.txt 127.0.0.1 9001
feeder marketdata.txt 127.0.0.1 9002
feeder trades.txt 127.0.0.1 9003
feeder inquiries.txt 127.0.0.1 9004
```

---

## 9. Notes

```md
## 9. Notes
- Inbound connectors parse newline-delimited messages and can accept long-lived connections.
- All inbound price fields are read as fractional and converted to decimal internally.
- All historical/GUI price output is written back in fractional format.
```

## Appendix: Change of base codes

Change of base codes:
Add a function:
executionservice.cpp add a function:

```cpp
template<typename T>
PricingSide ExecutionOrder<T>::GetSide() const
{
    return side;
}