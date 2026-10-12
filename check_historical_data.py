
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta, timezone
from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY
import csv
import openpyxl
import time

EXCEL_FILE = "Final_Algorithmic_Trading_Portfolio_36_Stocks_Final_WDC.xlsx"

# Enter your PAPER API credentials when prompted
api_key = ALPACA_API_KEY
api_secret = ALPACA_SECRET_KEY

client = StockHistoricalDataClient(api_key, api_secret)

# Read all 36 tickers from your submitted portfolio
wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
ws = wb["Final Portfolio"]

stocks = []
for row in range(5, 41):
    ticker = ws.cell(row, 2).value
    member = ws.cell(row, 4).value
    if ticker:
        stocks.append((str(ticker).strip().upper(), member))

# Request the previous 30 calendar days, ending before today.
end = datetime.now(timezone.utc) - timedelta(days=1)
start = end - timedelta(days=30)

results = []

for ticker, member in stocks:
    try:
        request = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=1000,
        )

        bars = client.get_stock_bars(request).df

        if bars.empty:
            print(f"{ticker}: NO DATA RETURNED")
            results.append({
                "Member": member,
                "Ticker": ticker,
                "Bars": 0,
                "OHLCV_Complete": False,
                "Result": "NO DATA RETURNED",
            })
            continue

        # For a single ticker, Alpaca may return a MultiIndex DataFrame.
        if "symbol" in bars.index.names:
            ticker_bars = bars.xs(ticker, level="symbol")
        else:
            ticker_bars = bars

        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in ticker_bars.columns]

        if missing:
            complete = False
            result = "MISSING COLUMNS: " + ", ".join(missing)
        else:
            complete = (
                not ticker_bars[required].isnull().any().any()
                and len(ticker_bars) > 0
            )
            result = "DATA AVAILABLE" if complete else "INCOMPLETE OHLCV"

        print(f"{ticker}: {result} ({len(ticker_bars)} daily bars)")

        # Save the actual OHLCV data for this ticker
        ticker_bars.to_csv(f"{ticker}_daily_ohlcv.csv")

        results.append({
            "Member": member,
            "Ticker": ticker,
            "Bars": len(ticker_bars),
            "OHLCV_Complete": complete,
            "Result": result,
        })

        time.sleep(0.25)

    except Exception as error:
        print(f"{ticker}: CHECK FAILED - {type(error).__name__}: {error}")
        results.append({
            "Member": member,
            "Ticker": ticker,
            "Bars": 0,
            "OHLCV_Complete": False,
            "Result": f"CHECK FAILED: {type(error).__name__}: {error}",
        })

with open(
    "alpaca_historical_data_check.csv",
    "w",
    newline="",
    encoding="utf-8",
) as file:
    fields = ["Member", "Ticker", "Bars", "OHLCV_Complete", "Result"]
    writer = csv.DictWriter(file, fieldnames=fields)
    writer.writeheader()
    writer.writerows(results)

passed = sum(r["OHLCV_Complete"] is True for r in results)

print("\n========== FINAL SUMMARY ==========")
print(f"Stocks checked: {len(results)}")
print(f"Stocks with complete OHLCV: {passed}")
print(f"Stocks requiring investigation: {len(results) - passed}")
print("Summary report: alpaca_historical_data_check.csv")
print("Individual daily files: TICKER_daily_ohlcv.csv")
