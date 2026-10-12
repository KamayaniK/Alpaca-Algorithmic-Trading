
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY


ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

TICKERS = [
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
]

OHLCV = ["open", "high", "low", "close", "volume"]

# Simple calendar-day freshness threshold.
# Market holidays and weekends are not accounted for separately.
MAX_DATA_AGE_CALENDAR_DAYS = 5


def main():
    client = TradingClient(
        ALPACA_API_KEY,
        ALPACA_SECRET_KEY,
        paper=True,
    )

    # Retrieve Alpaca asset information.
    try:
        assets = client.get_all_assets(
            GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
        )
        asset_map = {asset.symbol: asset for asset in assets}
        asset_error = None

    except Exception as exc:
        asset_map = {}
        asset_error = str(exc)
        print("WARNING: Could not retrieve asset list:", asset_error)

    results = []

    for ticker in TICKERS:
        path = ROOT / f"{ticker}_daily_ohlcv_100.csv"
        issues = []

        row = {
            "ticker": ticker,
            "file_exists": path.exists(),
            "asset_found": ticker in asset_map,
            "tradable": None,
            "rows": 0,
            "first_timestamp": None,
            "latest_timestamp": None,
            "calendar_days_old": None,
            "missing_ohlcv_values": None,
            "duplicate_timestamps": None,
            "ohlcv_valid": False,
            "status": "FAIL",
            "notes": "",
        }

        # An API lookup failure means asset status is inconclusive.
        if asset_error:
            issues.append("Asset lookup inconclusive: API request failed")

        asset = asset_map.get(ticker)

        if asset is not None:
            row["tradable"] = bool(asset.tradable)
            status_value = getattr(asset.status, "value", asset.status)

            if str(status_value).lower() != "active":
                issues.append(f"Asset status is {status_value}")

            if not asset.tradable:
                issues.append("Asset is not tradable")

        elif not asset_error:
            issues.append("Ticker not found in Alpaca asset list")

        # Check whether the local history file exists.
        if not path.exists():
            issues.append("History CSV is missing")
            row["notes"] = "; ".join(issues)
            row["status"] = "REVIEW"
            results.append(row)

            print(f"{ticker}: MISSING FILE")
            continue

        try:
            df = pd.read_csv(path)
            df.columns = [str(col).lower() for col in df.columns]
            row["rows"] = len(df)

            required = ["timestamp"] + OHLCV
            missing_columns = sorted(set(required) - set(df.columns))

            if missing_columns:
                issues.append(f"Missing columns: {missing_columns}")
                row["notes"] = "; ".join(issues)
                row["status"] = "REVIEW"
                results.append(row)

                print(f"{ticker}: missing columns {missing_columns}")
                continue

            # Normalize timestamps and numeric columns.
            df["timestamp"] = pd.to_datetime(
                df["timestamp"],
                utc=True,
                errors="coerce",
            )

            for col in OHLCV:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            # Check timestamp coverage and freshness.
            row["first_timestamp"] = str(df["timestamp"].min())
            latest = df["timestamp"].max()
            row["latest_timestamp"] = str(latest)

            if pd.isna(latest):
                issues.append("No valid timestamps found")
            else:
                age = datetime.now(timezone.utc) - latest.to_pydatetime()
                row["calendar_days_old"] = age.days

                if age.days > MAX_DATA_AGE_CALENDAR_DAYS:
                    issues.append(
                        f"Stale data: latest bar is {age.days} "
                        "calendar days old"
                    )

            # Check missing/invalid values and duplicate timestamps.
            row["missing_ohlcv_values"] = int(
                df[required].isna().any(axis=1).sum()
            )

            row["duplicate_timestamps"] = int(
                df["timestamp"].duplicated().sum()
            )

            if row["missing_ohlcv_values"] > 0:
                issues.append("Missing or invalid OHLCV/timestamp values")

            if row["duplicate_timestamps"] > 0:
                issues.append("Duplicate timestamps")

            # Check OHLC prices and volume.
            prices = df[["open", "high", "low", "close"]]

            if (prices <= 0).any().any():
                issues.append("Non-positive prices")

            if (df["volume"] < 0).any():
                issues.append("Negative volume")

            if (
                df["high"]
                < prices[["open", "low", "close"]].max(axis=1)
            ).any():
                issues.append("High below another OHLC price")

            if (
                df["low"]
                > prices[["open", "high", "close"]].min(axis=1)
            ).any():
                issues.append("Low above another OHLC price")

            # OHLCV validity is separate from freshness and asset status.
            invalid_ohlcv_messages = [
                "Missing or invalid OHLCV/timestamp values",
                "Duplicate timestamps",
                "Non-positive prices",
                "Negative volume",
                "High below another OHLC price",
                "Low above another OHLC price",
            ]

            row["ohlcv_valid"] = not any(
                message in issues
                for message in invalid_ohlcv_messages
            )

        except Exception as exc:
            issues.append(f"Could not validate CSV: {exc}")

        # Overall status includes data freshness and asset checks.
        row["status"] = "PASS" if not issues else "REVIEW"
        row["notes"] = "; ".join(issues) if issues else "Checks passed"

        results.append(row)

        print(
            f"{ticker}: rows={row['rows']}, "
            f"asset_found={row['asset_found']}, "
            f"tradable={row['tradable']}, "
            f"ohlcv_valid={row['ohlcv_valid']}, "
            f"data_age_days={row['calendar_days_old']}, "
            f"status={row['status']}, "
            f"notes={row['notes']}"
        )

    # Save timestamped CSV and Markdown reports.
    report = pd.DataFrame(results)

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_UTC"
    )

    csv_path = REPORTS / f"all_36_validation_{timestamp}.csv"
    md_path = REPORTS / f"all_36_validation_{timestamp}.md"

    report.to_csv(csv_path, index=False)

    with md_path.open("w", encoding="utf-8") as file:
        file.write("# Team 36-Stock Data Validation\n\n")
        file.write(f"- Generated (UTC): {timestamp}\n")
        file.write(
            "- Source: local history CSVs and Alpaca asset lookup\n"
        )
        file.write(
            f"- Maximum calendar-day data age: "
            f"{MAX_DATA_AGE_CALENDAR_DAYS}\n"
        )
        file.write(
            "- Freshness uses calendar days, so weekends and market "
            "holidays are not handled separately.\n"
        )
        file.write(
            "- Failed Alpaca asset lookup is marked inconclusive.\n\n"
        )
        file.write(report.to_markdown(index=False))
        file.write("\n")

    # Print final summary.
    print("\n" + "=" * 55)
    print("VALIDATION SUMMARY")
    print("=" * 55)
    print("Total tickers:", len(report))
    print("PASS:", int((report["status"] == "PASS").sum()))
    print("Needs review:", int((report["status"] == "REVIEW").sum()))
    print("Missing files:", int((~report["file_exists"]).sum()))
    print("Valid OHLCV files:", int(report["ohlcv_valid"].sum()))
    print("CSV report:", csv_path.relative_to(ROOT))
    print("Markdown report:", md_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
