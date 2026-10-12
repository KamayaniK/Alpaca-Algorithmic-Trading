
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


def main():
    client = TradingClient(
        ALPACA_API_KEY,
        ALPACA_SECRET_KEY,
        paper=True,
    )

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

        if not path.exists():
            issues.append("History CSV is missing")
            row["notes"] = "; ".join(issues)
            results.append(row)
            print(f"{ticker}: MISSING FILE")
            continue

        try:
            df = pd.read_csv(path)
            df.columns = [str(c).lower() for c in df.columns]
            row["rows"] = len(df)

            required = ["timestamp"] + OHLCV
            missing_columns = sorted(set(required) - set(df.columns))
            if missing_columns:
                issues.append(f"Missing columns: {missing_columns}")
                row["notes"] = "; ".join(issues)
                results.append(row)
                print(f"{ticker}: missing columns {missing_columns}")
                continue

            df["timestamp"] = pd.to_datetime(
                df["timestamp"], utc=True, errors="coerce"
            )
            for col in OHLCV:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            row["first_timestamp"] = str(df["timestamp"].min())
            latest = df["timestamp"].max()
            row["latest_timestamp"] = str(latest)

            if pd.notna(latest):
                row["calendar_days_old"] = (
                    datetime.now(timezone.utc) - latest.to_pydatetime()
                ).days

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

            prices = df[["open", "high", "low", "close"]]
            if (prices <= 0).any().any():
                issues.append("Non-positive prices")
            if (df["volume"] < 0).any():
                issues.append("Negative volume")
            if (df["high"] < prices[["open", "low", "close"]].max(axis=1)).any():
                issues.append("High below another OHLC price")
            if (df["low"] > prices[["open", "high", "close"]].min(axis=1)).any():
                issues.append("Low above another OHLC price")

            row["ohlcv_valid"] = not any(
                message in issues for message in [
                    "Missing or invalid OHLCV/timestamp values",
                    "Duplicate timestamps",
                    "Non-positive prices",
                    "Negative volume",
                    "High below another OHLC price",
                    "Low above another OHLC price",
                ]
            )

        except Exception as exc:
            issues.append(f"Could not validate CSV: {exc}")

        row["status"] = "PASS" if not issues else "REVIEW"
        row["notes"] = "; ".join(issues) if issues else "Checks passed"
        results.append(row)

        print(
            f"{ticker}: rows={row['rows']}, "
            f"asset_found={row['asset_found']}, "
            f"tradable={row['tradable']}, "
            f"ohlcv_valid={row['ohlcv_valid']}, "
            f"status={row['status']}, notes={row['notes']}"
        )

    report = pd.DataFrame(results)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
    csv_path = REPORTS / f"all_36_validation_{timestamp}.csv"
    md_path = REPORTS / f"all_36_validation_{timestamp}.md"

    report.to_csv(csv_path, index=False)

    with md_path.open("w", encoding="utf-8") as f:
        f.write("# Team 36-Stock Data Validation\n\n")
        f.write(f"- Generated (UTC): {timestamp}\n")
        f.write("- Source: local longer-history CSVs and Alpaca asset lookup\n")
        f.write("- Freshness is reported as calendar-day age; this does not account for market holidays.\n")
        f.write("- A failed asset API lookup is marked inconclusive, not as an invalid ticker.\n\n")
        f.write(report.to_markdown(index=False))
        f.write("\n")

    print("\nValidation summary")
    print("Total:", len(report))
    print("PASS:", int((report["status"] == "PASS").sum()))
    print("Needs review:", int((report["status"] == "REVIEW").sum()))
    print("CSV report:", csv_path.relative_to(ROOT))
    print("Markdown report:", md_path.relative_to(ROOT))


if __name__ == "__main__":
    main()
