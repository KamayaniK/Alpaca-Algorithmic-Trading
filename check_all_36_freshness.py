
from pathlib import Path
import pandas as pd

TICKERS = [
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV"
]

ROOT = Path(__file__).resolve().parent

for ticker in TICKERS:
    path = ROOT / f"{ticker}_daily_ohlcv_100.csv"

    try:
        df = pd.read_csv(path)

        if df.empty:
            print(f"CHECK {ticker}: file is empty")
            continue

        timestamp_column = next(
            (column for column in ("timestamp", "date", "datetime")
             if column in df.columns),
            None
        )

        if timestamp_column is None:
            print(f"CHECK {ticker}: timestamp/date column not found")
            continue

        latest = pd.to_datetime(
            df[timestamp_column], errors="coerce", utc=True
        ).max()

        print(
            f"{ticker}: rows={len(df)}, "
            f"latest={latest if pd.notna(latest) else 'INVALID TIMESTAMP'}"
        )

    except Exception as error:
        print(f"CHECK {ticker}: {error}")
