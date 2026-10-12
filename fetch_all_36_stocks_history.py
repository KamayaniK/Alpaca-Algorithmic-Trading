
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY

ROOT = Path(__file__).resolve().parent

TICKERS = [
    # Mahi
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    # Aashima
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    # Kamya
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
]

DAYS_BACK = 220
client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)


def save_symbol_frame(symbol, frame):
    frame = frame.reset_index()
    frame.columns = [str(c).lower() for c in frame.columns]

    # Use the same filename convention as your existing longer-history files.
    path = ROOT / f"{symbol}_daily_ohlcv_100.csv"
    frame.to_csv(path, index=False)

    latest = pd.to_datetime(frame["timestamp"], utc=True).max()
    print(f"{symbol}: saved {len(frame)} bars; latest={latest}; file={path.name}")


def fetch_individually(symbol, start, end):
    for attempt in range(1, 4):
        try:
            request = StockBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                limit=1000,
                feed="iex",
            )
            bars = client.get_stock_bars(request).df

            if bars.empty:
                print(f"{symbol}: no bars returned (attempt {attempt}/3)")
            else:
                if isinstance(bars.index, pd.MultiIndex):
                    bars = bars.xs(symbol, level="symbol")
                save_symbol_frame(symbol, bars)
                return True

        except Exception as exc:
            print(f"{symbol}: attempt {attempt}/3 failed: {exc}")

        if attempt < 3:
            time.sleep(attempt * 2)

    print(f"{symbol}: FAILED after retries")
    return False


def main():
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=DAYS_BACK)
    succeeded = set()
    failed = set(TICKERS)

    print(f"Fetching {len(TICKERS)} stocks from Alpaca IEX.")
    print(f"Requested window: {start.isoformat()} to {end.isoformat()}")
    print("Existing original *_daily_ohlcv.csv files will not be changed.")

    # First attempt: batch request for all 36 symbols.
    try:
        request = StockBarsRequest(
            symbol_or_symbols=TICKERS,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=1000,
            feed="iex",
        )
        batch = client.get_stock_bars(request).df

        if not batch.empty and isinstance(batch.index, pd.MultiIndex):
            returned = set(batch.index.get_level_values("symbol").unique())

            for symbol in TICKERS:
                if symbol in returned:
                    frame = batch.xs(symbol, level="symbol")
                    if not frame.empty:
                        save_symbol_frame(symbol, frame)
                        succeeded.add(symbol)
                        failed.discard(symbol)

        print(f"Batch returned data for {len(succeeded)}/{len(TICKERS)} stocks.")

    except Exception as exc:
        print(f"Batch request failed; will retry stocks individually: {exc}")

    # Retry missing symbols individually to handle partial batch responses.
    for symbol in TICKERS:
        if symbol in failed:
            if fetch_individually(symbol, start, end):
                succeeded.add(symbol)
                failed.discard(symbol)

    report_dir = ROOT / "reports"
    report_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")

    report = pd.DataFrame([
        {"ticker": symbol, "download_status": "saved" if symbol in succeeded else "failed"}
        for symbol in TICKERS
    ])
    report_path = report_dir / f"all_36_fetch_{timestamp}.csv"
    report.to_csv(report_path, index=False)

    print("\nFetch summary")
    print(f"Succeeded: {len(succeeded)}/{len(TICKERS)}")
    print(f"Failed: {sorted(failed)}")
    print(f"Summary report: {report_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
