# Member 1 — Market Data & MCP Handoff

## 1. Purpose

This component provides historical stock market data, technical indicators, data validation, and a local MCP server for the algorithmic trading agents project.

## 2. Stock Universe

The data pipeline supports 36 stocks assigned across the three project members.

Historical daily OHLCV files use the naming convention:

`TICKER_daily_ohlcv_100.csv`

These files contain daily market bars. The suffix `_100` is a filename convention and does not guarantee exactly 100 rows.

## 3. Data Source

- Provider: Alpaca Market Data API
- Feed: IEX
- Timeframe: Daily bars
- Latest verified historical timestamp: October 9, 2026
- Latest checked history: 150 rows per stock

**Data limitation:** The IEX feed is used because the project's current Alpaca subscription did not permit the requested recent SIP data. Feed coverage may differ from SIP.

## 4. Technical Indicators

The indicator module is:

`indicators/technical_indicators.py`

It calculates:

- EMA 20
- EMA 50
- RSI 14
- MACD
- MACD Signal
- ATR 14

The output also includes market-bar fields such as timestamp, open, high, low, close, and volume where available.

## 5. Local MCP Server

Server file:

`technical_indicators_mcp_server.py`

Available tools:

| Tool | Purpose |
|---|---|
| `get_account_summary` | Reads Alpaca paper-account status |
| `get_stock_bars` | Retrieves daily OHLCV bars from Alpaca IEX |
| `calculate_stock_indicators` | Calculates indicators from a local historical CSV |
| `validate_local_stock_data` | Checks local OHLCV data quality |

The server communicates through the MCP client using standard input/output.

## 6. Validation Evidence

Latest checks recorded on October 12, 2026:

- Historical data fetch: 36/36 stocks succeeded
- Data validation: 36 passed, 0 needing review
- Indicator calculations: 36 passed, 0 failed
- Four-tool MCP client test: 4 passed, 0 failed
- 36-stock MCP indicator test: 36 passed, 0 failed

Reports are stored in the `reports/` directory.

## 7. How to Run the Tests

From the project root, run:

`python validate_all_36_stocks.py`

`python save_all_36_indicator_report.py`

`python test_mcp_client.py`

## 8. Integration Notes for Member 2

- Consume the MCP tools through the MCP client rather than relying on direct imports from the server.
- Check each tool's returned content and error status before using the data.
- Use the returned timestamps to verify data freshness.
- Agree on the exact output schema before connecting the data tools to CrewAI.
- Treat indicator outputs as inputs to a strategy, not as guaranteed BUY or SELL recommendations.

## 9. Security and Limitations

- Never commit API keys or secret keys to GitHub.
- Use paper trading during testing.
- Data validation does not guarantee that every expected trading session is present.
- Historical indicator tests do not establish profitability.
- No order execution is performed by these four MCP tools.
