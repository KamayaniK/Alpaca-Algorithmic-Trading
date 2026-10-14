"""
Stage consistently adjusted Alpaca daily bars for the portfolio backtest.
This script NEVER overwrites existing backtest CSVs.
Run from the project root with the project's .venv activated:
    python stage_adjusted_history.py
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from alpaca.data.enums import Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY

ROOT = Path(__file__).resolve().parent
TICKERS = [
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN", "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN", "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL", "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
    "SPY",
]
DAYS_BACK = 220
MIN_ROWS_PER_SYMBOL = 60
RETRIES = 3
FEED = "iex"

def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
    stage = ROOT / f"adjusted_data_staging_{stamp}"
    stage.mkdir(parents=True, exist_ok=False)

    client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=DAYS_BACK)
    manifest: dict[str, object] = {
        "adjustment": Adjustment.ALL.value,
        "feed": FEED,
        "start_requested_utc": start.isoformat(),
        "end_requested_utc": end.isoformat(),
        "staging_directory": stage.name,
        "files": {},
        "errors": {},
        "replacement_performed": False,
    }

    print(f"Staging {len(TICKERS)} symbols with adjustment=ALL, feed={FEED}")
    print(f"Requested range: {start.isoformat()} to {end.isoformat()}")
    print(f"Staging directory: {stage}")

    for symbol in TICKERS:
        success = False
        for attempt in range(1, RETRIES + 1):
            try:
                request = StockBarsRequest(
                    symbol_or_symbols=[symbol],
                    timeframe=TimeFrame.Day,
                    start=start,
                    end=end,
                    limit=1000,
                    feed=FEED,
                    adjustment=Adjustment.ALL,
                )
                bars = client.get_stock_bars(request).df
                if bars.empty:
                    raise ValueError("No bars returned")
                if isinstance(bars.index, pd.MultiIndex):
                    if symbol not in bars.index.get_level_values("symbol"):
                        raise ValueError(f"No bars returned for {symbol}")
                    bars = bars.xs(symbol, level="symbol")

                frame = bars.reset_index()
                frame.columns = [str(c).lower() for c in frame.columns]
                required = {"timestamp", "open", "high", "low", "close", "volume"}
                missing = required - set(frame.columns)
                if missing:
                    raise ValueError(f"Missing columns: {sorted(missing)}")

                frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
                for col in ("open", "high", "low", "close", "volume"):
                    frame[col] = pd.to_numeric(frame[col], errors="coerce")
                frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close"])
                frame = frame.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
                if len(frame) < MIN_ROWS_PER_SYMBOL:
                    raise ValueError(f"Only {len(frame)} valid rows; need at least {MIN_ROWS_PER_SYMBOL}")
                if (frame[["open", "high", "low", "close"]] <= 0).any().any():
                    raise ValueError("Non-positive OHLC price found")
                if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
                    raise ValueError("Invalid high/low OHLC relationship")
                if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
                    raise ValueError("Invalid low/high OHLC relationship")

                out_path = stage / f"{symbol}_daily_ohlcv_100.csv"
                frame.to_csv(out_path, index=False)
                manifest["files"][symbol] = {
                    "filename": out_path.name,
                    "rows": int(len(frame)),
                    "first_timestamp": frame["timestamp"].min().isoformat(),
                    "last_timestamp": frame["timestamp"].max().isoformat(),
                    "adjustment": Adjustment.ALL.value,
                }
                print(f"OK {symbol}: {len(frame)} bars; {frame['timestamp'].min()} -> {frame['timestamp'].max()}")
                success = True
                break
            except Exception as exc:
                print(f"{symbol}: attempt {attempt}/{RETRIES} failed: {exc}")
                if attempt < RETRIES:
                    time.sleep(attempt * 2)

        if not success:
            manifest["errors"][symbol] = "Failed after retries; see console output"

    # Require the exact universe, sufficient shared history, and a clean file set.
    written = set(manifest["files"].keys())
    all_ok = written == set(TICKERS) and not manifest["errors"]
    if all_ok:
        frames = {s: pd.read_csv(stage / f"{s}_daily_ohlcv_100.csv", usecols=["timestamp"])
                  for s in TICKERS}
        common_dates = None
        for frame in frames.values():
            dates = set(pd.to_datetime(frame["timestamp"], utc=True).dropna())
            common_dates = dates if common_dates is None else common_dates & dates
        common_count = len(common_dates or set())
        manifest["common_date_count"] = common_count
        manifest["validation_passed"] = common_count >= MIN_ROWS_PER_SYMBOL
        if common_count < MIN_ROWS_PER_SYMBOL:
            manifest["errors"]["common_dates"] = (
                f"Only {common_count} common dates; need at least {MIN_ROWS_PER_SYMBOL}"
            )
    else:
        manifest["validation_passed"] = False

    manifest_path = stage / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nManifest: {manifest_path}")
    print(f"Symbols staged: {len(written)}/{len(TICKERS)}")
    print(f"Validation passed: {manifest.get('validation_passed', False)}")
    print("Existing backtest input files were NOT modified.")

    return 0 if manifest.get("validation_passed", False) else 1

if __name__ == "__main__":
    raise SystemExit(main())
