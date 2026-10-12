
from datetime import datetime, timedelta, timezone

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

end = datetime.now(timezone.utc)
start = end - timedelta(days=220)

request = StockBarsRequest(
    symbol_or_symbols=["SNDK"],
    timeframe=TimeFrame.Day,
    start=start,
    end=end,
    limit=1000,
    feed="iex",
)

print("Requesting SNDK history individually using IEX...")
bars = client.get_stock_bars(request).df

if bars.empty:
    print("RESULT: Alpaca returned no SNDK bars.")
else:
    print("RESULT: Historical bars received.")
    print("Rows:", len(bars))
    print("First timestamp:", bars.index.get_level_values("timestamp").min())
    print("Last timestamp:", bars.index.get_level_values("timestamp").max())
