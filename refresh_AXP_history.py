
from datetime import datetime, timedelta, timezone
from pathlib import Path
import time

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "AXP_daily_ohlcv_100.csv"
BACKUP = ROOT / "AXP_daily_ohlcv_100_before_refresh.csv"

client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)


def main():
    # Preserve the existing file before attempting a refresh.
    if OUTPUT.exists() and not BACKUP.exists():
        pd.read_csv(OUTPUT).to_csv(BACKUP, index=False)
        print(f"Backup saved: {BACKUP.name}")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=220)

    print("Requesting AXP daily bars from Alpaca IEX.")
    print(f"Window: {start.isoformat()} to {end.isoformat()}")

    for attempt in range(1, 4):
        try:
            request = StockBarsRequest(
                symbol_or_symbols=["AXP"],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                limit=1000,
                feed="iex",
            )

            bars = client.get_stock_bars(request).df

            if bars.empty:
                raise ValueError("Alpaca returned no AXP bars.")

            if isinstance(bars.index, pd.MultiIndex):
                bars = bars.xs("AXP", level="symbol")

            refreshed = bars.reset_index()
            refreshed.columns = [
                str(column).lower()
                for column in refreshed.columns
            ]

            if "timestamp" not in refreshed.columns:
                raise ValueError("Timestamp column is missing.")

            latest = pd.to_datetime(
                refreshed["timestamp"], utc=True, errors="coerce"
            ).max()

            print(f"Bars returned: {len(refreshed)}")
            print(f"Latest timestamp: {latest}")

            # Refuse to replace the file if the result is still stale.
            if pd.isna(latest) or latest.date() < (
                end.date() - timedelta(days=5)
            ):
                raise ValueError(
                    "Returned data is still stale. "
                    "Existing file will be preserved."
                )

            # Save to a temporary file first, then replace the target.
            temporary = OUTPUT.with_suffix(".tmp.csv")
            refreshed.to_csv(temporary, index=False)
            pd.read_csv(temporary)  # Confirm the temporary CSV is readable.
            temporary.replace(OUTPUT)

            print(f"SUCCESS: Updated {OUTPUT.name}")
            print(f"Backup retained: {BACKUP.name}")
            return

        except Exception as error:
            print(f"Attempt {attempt}/3 failed: {error}")
            if attempt < 3:
                time.sleep(attempt * 2)

    print("FAILED: AXP file was not refreshed successfully.")


if __name__ == "__main__":
    main()
