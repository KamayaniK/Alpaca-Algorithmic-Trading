
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY


MY_STOCKS = [
    "SNDK", "AMD", "APP", "MRNA",
    "GOOGL", "AMZN", "JPM", "LLY",
    "META", "XOM", "PEP", "ABT",
]


if (
    not ALPACA_API_KEY
    or not ALPACA_SECRET_KEY
    or "..." in ALPACA_API_KEY
    or "..." in ALPACA_SECRET_KEY
):
    raise ValueError(
        "Check alpaca_credentials.py for your real paper-trading "
        "credentials. Never share your keys."
    )


client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)

end = datetime.now(timezone.utc)
start = end - timedelta(days=220)
project_root = Path(__file__).resolve().parent


def download_one_stock(ticker):
    """Download one ticker's daily bars using the IEX feed."""
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
        return None

    # Extract the ticker if Alpaca returns a MultiIndex.
    if isinstance(bars.index, pd.MultiIndex):
        symbols = set(bars.index.get_level_values("symbol"))
        if ticker not in symbols:
            return None
        bars = bars.xs(ticker, level="symbol")

    bars = bars.reset_index()
    bars.columns = [str(column).lower() for column in bars.columns]

    return bars


print("Downloading daily history for Mahi's 12 stocks...")
print("Feed: IEX")
print("Requesting all 12 stocks together first.\n")


# First, try a single batch request.
batch_bars = None

try:
    batch_request = StockBarsRequest(
        symbol_or_symbols=MY_STOCKS,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        limit=1000,
        feed="iex",
    )

    batch_bars = client.get_stock_bars(batch_request).df

except Exception as exc:
    print(f"Batch request failed: {exc}")
    print("Will try each stock individually.\n")


if batch_bars is not None and not batch_bars.empty:
    if isinstance(batch_bars.index, pd.MultiIndex):
        available_symbols = set(
            batch_bars.index.get_level_values("symbol")
        )
        print("Symbols returned by batch:", sorted(available_symbols))
    else:
        available_symbols = set(MY_STOCKS)
else:
    available_symbols = set()


success_count = 0

for ticker in MY_STOCKS:
    try:
        stock_bars = None

        # Use the batch result if this ticker was returned.
        if (
            batch_bars is not None
            and not batch_bars.empty
            and ticker in available_symbols
        ):
            if isinstance(batch_bars.index, pd.MultiIndex):
                stock_bars = batch_bars.xs(
                    ticker, level="symbol"
                ).copy()
                stock_bars = stock_bars.reset_index()
                stock_bars.columns = [
                    str(column).lower() for column in stock_bars.columns
                ]
            else:
                stock_bars = batch_bars.copy()

        # Retry missing tickers individually.
        if stock_bars is None or stock_bars.empty:
            print(f"{ticker}: Missing from batch; retrying individually...")
            stock_bars = download_one_stock(ticker)

        if stock_bars is None or stock_bars.empty:
            print(f"{ticker}: NO DATA returned after retry.")
            continue

        output_path = (
            project_root / f"{ticker}_daily_ohlcv_100.csv"
        )
        stock_bars.to_csv(output_path, index=False)

        success_count += 1
        print(
            f"{ticker}: {len(stock_bars)} bars saved "
            f"to {output_path.name}"
        )

    except Exception as exc:
        print(f"{ticker}: FAILED - {exc}")


print(f"\nDownload finished: {success_count}/{len(MY_STOCKS)} stocks saved.")
print("Original *_daily_ohlcv.csv files were not changed.")
