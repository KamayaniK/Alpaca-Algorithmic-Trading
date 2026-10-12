
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta, timezone
from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY
import time

client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

end = datetime.now(timezone.utc) - timedelta(days=1)
start = end - timedelta(days=30)

for ticker in ["SNDK", "AMD"]:
    success = False

    for attempt in range(1, 4):
        try:
            request = StockBarsRequest(
                symbol_or_symbols=ticker,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                limit=1000,
            )

            bars = client.get_stock_bars(request).df

            if not bars.empty:
                bars.to_csv(f"{ticker}_daily_ohlcv.csv")
                print(
                    f"{ticker}: DATA AVAILABLE "
                    f"({len(bars)} rows), attempt {attempt}"
                )
                success = True
                break

            print(f"{ticker}: No bars returned, attempt {attempt}")

        except Exception as error:
            print(
                f"{ticker}: Attempt {attempt} failed - "
                f"{type(error).__name__}: {error}"
            )

        if attempt < 3:
            time.sleep(5)

    if not success:
        print(f"{ticker}: STILL UNVERIFIED — investigate further")
