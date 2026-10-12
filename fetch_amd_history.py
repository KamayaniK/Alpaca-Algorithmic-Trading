
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import the exact variable names from your existing credentials file.
from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY

if (
    not ALPACA_API_KEY
    or not ALPACA_SECRET_KEY
    or "..." in ALPACA_API_KEY
    or "..." in ALPACA_SECRET_KEY
):
    raise ValueError(
        "Your Alpaca credentials appear to be placeholders. "
        "Update alpaca_credentials.py with your real paper-trading keys."
    )

client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

ticker = "AMD"
end = datetime.now(timezone.utc)
start = end - timedelta(days=220)

request = StockBarsRequest(
    symbol_or_symbols=[ticker],
    timeframe=TimeFrame.Day,
    start=start,
    end=end,
    limit=1000,
    feed="iex",
)

bars = client.get_stock_bars(request).df

if bars.empty:
    raise RuntimeError(
        f"No historical bars returned for {ticker}. "
        "Check your data access and date range."
    )

# Convert Alpaca's response into a regular DataFrame.
if isinstance(bars.index, pd.MultiIndex):
    bars = bars.xs(ticker, level="symbol")

bars = bars.reset_index()
bars.columns = [str(column).lower() for column in bars.columns]

project_root = Path(__file__).resolve().parent
output_path = project_root / f"{ticker}_daily_ohlcv_100.csv"

bars.to_csv(output_path, index=False)

print("\nHistorical data download successful.")
print("Ticker:", ticker)
print("Daily bars downloaded:", len(bars))
print("First timestamp:", bars["timestamp"].min())
print("Last timestamp:", bars["timestamp"].max())
print("Saved file:", output_path.name)
