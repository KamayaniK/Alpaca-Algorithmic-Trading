
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY


MY_STOCKS = [
    "SNDK", "AMD", "APP", "MRNA",
    "GOOGL", "AMZN", "JPM", "LLY",
    "META", "XOM", "PEP", "ABT",
]

project_root = Path(__file__).resolve().parent
reports_dir = project_root / "reports"
reports_dir.mkdir(exist_ok=True)

# These are daily bars, so the most recent completed trading
# session is the relevant freshness reference.
today_utc = datetime.now(timezone.utc).date()

client = TradingClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    paper=True,
)

print("Validating Mahi's 12 stocks")
print("This script does not place orders.\n")

asset_by_symbol = {}

try:
    request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
    assets = client.get_all_assets(request)

    asset_by_symbol = {
        asset.symbol: asset for asset in assets
        if asset.symbol in MY_STOCKS
    }
except Exception as exc:
    print(f"WARNING: Could not retrieve asset list: {exc}")

results = []

for ticker in MY_STOCKS:
    row = {
        "ticker": ticker,
        "asset_found": False,
        "asset_status": "UNKNOWN",
        "tradable": None,
        "csv_found": False,
        "row_count": 0,
        "first_bar": "",
        "last_bar": "",
        "calendar_days_since_last_bar": None,
        "missing_ohlcv_values": None,
        "duplicate_timestamps": None,
        "ohlcv_valid": False,
        "notes": "",
    }

    notes = []

    # 1. Check Alpaca asset availability.
    asset = asset_by_symbol.get(ticker)

    if asset is None:
        notes.append("Ticker not found in returned asset list")
    else:
        row["asset_found"] = True
        row["asset_status"] = str(asset.status)
        row["tradable"] = bool(asset.tradable)

        status_value = getattr(asset.status, "value", asset.status)

        if str(status_value).lower() != "active":
            notes.append(f"Asset status is {status_value}")
        if not asset.tradable:
            notes.append("Asset is not tradable")

    # 2. Prefer the longer-history CSV, fall back to the original.
    long_csv = project_root / f"{ticker}_daily_ohlcv_100.csv"
    original_csv = project_root / f"{ticker}_daily_ohlcv.csv"

    if long_csv.exists():
        csv_path = long_csv
    elif original_csv.exists():
        csv_path = original_csv
        notes.append("Using original CSV; longer-history CSV not found")
    else:
        notes.append("No OHLCV CSV file found")
        row["notes"] = "; ".join(notes)
        results.append(row)
        print(f"{ticker}: NO CSV")
        continue

    row["csv_found"] = True

    try:
        data = pd.read_csv(csv_path)
        row["row_count"] = len(data)

        data.columns = [str(col).strip().lower() for col in data.columns]

        required = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_columns = [col for col in required if col not in data.columns]

        if missing_columns:
            notes.append(
                "Missing columns: " + ", ".join(missing_columns)
            )
            row["notes"] = "; ".join(notes)
            results.append(row)
            print(f"{ticker}: INVALID CSV — missing columns")
            continue

        # Parse timestamps and numeric OHLCV fields.
        data["timestamp"] = pd.to_datetime(
            data["timestamp"], utc=True, errors="coerce"
        )

        for col in ["open", "high", "low", "close", "volume"]:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        # Count rows with missing or invalid required values.
        required_data = data[required]
        missing_values = int(required_data.isna().sum().sum())
        row["missing_ohlcv_values"] = missing_values

        # Count duplicate timestamps.
        duplicate_count = int(data["timestamp"].duplicated().sum())
        row["duplicate_timestamps"] = duplicate_count

        valid_timestamps = data["timestamp"].dropna()

        if not valid_timestamps.empty:
            first_bar = valid_timestamps.min()
            last_bar = valid_timestamps.max()

            row["first_bar"] = first_bar.isoformat()
            row["last_bar"] = last_bar.isoformat()
            row["calendar_days_since_last_bar"] = (
                today_utc - last_bar.date()
            ).days

            if row["calendar_days_since_last_bar"] > 5:
                notes.append("Latest daily bar is more than 5 calendar days old")

        # Basic price sanity checks.
        price_rows_valid = (
            (data["open"] > 0)
            & (data["high"] > 0)
            & (data["low"] > 0)
            & (data["close"] > 0)
            & (data["volume"] >= 0)
            & (data["high"] >= data["low"])
            & (data["high"] >= data["open"])
            & (data["high"] >= data["close"])
            & (data["low"] <= data["open"])
            & (data["low"] <= data["close"])
        )

        bad_price_rows = int((~price_rows_valid.fillna(False)).sum())

        if bad_price_rows:
            notes.append(f"{bad_price_rows} rows have invalid OHLCV values")

        row["ohlcv_valid"] = (
            missing_values == 0
            and duplicate_count == 0
            and bad_price_rows == 0
            and len(data) > 0
        )

        if missing_values:
            notes.append(f"{missing_values} missing required OHLCV values")
        if duplicate_count:
            notes.append(f"{duplicate_count} duplicate timestamps")

    except Exception as exc:
        notes.append(f"CSV validation error: {exc}")

    row["notes"] = "; ".join(notes) if notes else "Checks passed"
    results.append(row)

    print(
        f"{ticker}: rows={row['row_count']}, "
        f"asset_found={row['asset_found']}, "
        f"tradable={row['tradable']}, "
        f"ohlcv_valid={row['ohlcv_valid']}, "
        f"notes={row['notes']}"
    )


report = pd.DataFrame(results)
run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")

csv_path = reports_dir / f"mahi_data_validation_{run_id}.csv"
md_path = reports_dir / f"mahi_data_validation_{run_id}.md"

report.to_csv(csv_path, index=False)

with open(md_path, "w", encoding="utf-8") as file:
    file.write("# Mahi's Data Validation Report\n\n")
    file.write(f"- Run time (UTC): {run_id}\n")
    file.write("- Scope: Mahi's 12 assigned stocks\n")
    file.write("- Data source: local OHLCV CSV files and Alpaca asset metadata\n")
    file.write("- This report does not verify high-beta classifications.\n\n")
    file.write(report.to_markdown(index=False))
    file.write("\n")

print("\nValidation complete.")
print(f"CSV report: {csv_path.relative_to(project_root)}")
print(f"Markdown report: {md_path.relative_to(project_root)}")
print("High-beta evidence will be validated separately.")
