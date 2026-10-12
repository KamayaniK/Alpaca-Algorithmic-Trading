
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
from indicators.technical_indicators import calculate_indicators

TICKERS = [
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV"
]

root = Path(__file__).resolve().parent
reports_dir = root / "reports"
reports_dir.mkdir(exist_ok=True)

results = []

for ticker in TICKERS:
    path = root / f"{ticker}_daily_ohlcv_100.csv"

    try:
        if not path.exists():
            raise FileNotFoundError(f"Missing {path.name}")

        df = pd.read_csv(path)
        indicators = calculate_indicators(df)

        if indicators.empty:
            raise ValueError("No indicator rows returned")

        latest = indicators.iloc[-1]
        results.append({
            "ticker": ticker,
            "status": "PASS",
            "rows": len(indicators),
            "latest_close": latest["close"],
            "latest_rsi_14": latest["RSI_14"],
            "error": ""
        })

    except Exception as error:
        results.append({
            "ticker": ticker,
            "status": "FAIL",
            "rows": 0,
            "latest_close": None,
            "latest_rsi_14": None,
            "error": str(error)
        })

timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
csv_path = reports_dir / f"all_36_indicators_{timestamp}.csv"
md_path = reports_dir / f"all_36_indicators_{timestamp}.md"

report = pd.DataFrame(results)
report.to_csv(csv_path, index=False)

passed = (report["status"] == "PASS").sum()
failed = (report["status"] == "FAIL").sum()

with md_path.open("w", encoding="utf-8") as file:
    file.write("# All 36 Stocks — Indicator Validation\n\n")
    file.write(f"- Generated (UTC): {timestamp}\n")
    file.write(f"- Total stocks: {len(TICKERS)}\n")
    file.write(f"- Passed: {passed}\n")
    file.write(f"- Failed: {failed}\n\n")
    file.write("## Results\n\n")
    file.write(report.to_markdown(index=False))
    file.write(
        "\n\nNote: This report confirms indicator calculations completed; "
        "it does not establish strategy profitability or guarantee data accuracy.\n"
    )

print(f"Passed: {passed}/{len(TICKERS)}")
print(f"Failed: {failed}")
print(f"CSV report: {csv_path}")
print(f"Markdown report: {md_path}")
