
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY

ticker = "SPY"
client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

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
    raise RuntimeError("Alpaca returned no daily bars for SPY.")

if isinstance(bars.index, pd.MultiIndex):
    bars = bars.xs(ticker, level="symbol")

bars = bars.reset_index()
bars.columns = [str(column).lower() for column in bars.columns]

output_path = Path(__file__).resolve().parent / "SPY_daily_ohlcv.csv"
bars.to_csv(output_path, index=False)

print("SPY benchmark history downloaded.")
print("Rows:", len(bars))
print("First bar:", bars["timestamp"].min())
print("Latest bar:", bars["timestamp"].max())
print("Saved:", output_path.name)
