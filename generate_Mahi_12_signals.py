
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from indicators.technical_indicators import calculate_indicators


MY_STOCKS = [
    "SNDK", "AMD", "APP", "MRNA",
    "GOOGL", "AMZN", "JPM", "LLY",
    "META", "XOM", "PEP", "ABT",
]

project_root = Path(__file__).resolve().parent
reports_dir = project_root / "reports"
reports_dir.mkdir(exist_ok=True)

results = []

print("Generating signals for Mahi's 12 stocks")
print("This script does not place trades.\n")

for ticker in MY_STOCKS:
    csv_path = project_root / f"{ticker}_daily_ohlcv_100.csv"

    try:
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing file: {csv_path.name}")

        data = pd.read_csv(csv_path)
        indicators = calculate_indicators(data)

        if indicators.empty:
            raise ValueError("No valid price rows found.")

        latest = indicators.iloc[-1]

        required = [
            "close", "EMA_50", "RSI_14",
            "MACD", "MACD_Signal",
        ]

        missing = [
            column for column in required
            if column not in indicators.columns
            or pd.isna(latest[column])
        ]

        if missing:
            results.append({
                "ticker": ticker,
                "date": latest.get("timestamp", ""),
                "close": latest.get("close", float("nan")),
                "EMA_50": latest.get("EMA_50", float("nan")),
                "RSI_14": latest.get("RSI_14", float("nan")),
                "MACD": latest.get("MACD", float("nan")),
                "MACD_Signal": latest.get("MACD_Signal", float("nan")),
                "signal": "INSUFFICIENT DATA",
                "reason": "Missing: " + ", ".join(missing),
            })
            print(f"{ticker}: INSUFFICIENT DATA — {', '.join(missing)}")
            continue

        trend_ok = latest["close"] > latest["EMA_50"]
        momentum_ok = latest["MACD"] > latest["MACD_Signal"]
        rsi_ok = 50 <= latest["RSI_14"] <= 70

        if trend_ok and momentum_ok and rsi_ok:
            signal = "ENTRY CANDIDATE"
            reason = "Trend, momentum and RSI filters passed"
        else:
            signal = "NO ENTRY"
            reasons = []

            if not trend_ok:
                reasons.append("close not above EMA_50")
            if not momentum_ok:
                reasons.append("MACD not above signal")
            if not rsi_ok:
                reasons.append("RSI outside 50–70")

            reason = "; ".join(reasons)

        results.append({
            "ticker": ticker,
            "date": latest.get("timestamp", ""),
            "close": round(float(latest["close"]), 4),
            "EMA_50": round(float(latest["EMA_50"]), 4),
            "RSI_14": round(float(latest["RSI_14"]), 2),
            "MACD": round(float(latest["MACD"]), 4),
            "MACD_Signal": round(float(latest["MACD_Signal"]), 4),
            "signal": signal,
            "reason": reason,
        })

        print(
            f"{ticker}: {signal} | "
            f"Close={latest['close']:.2f} | "
            f"RSI={latest['RSI_14']:.2f}"
        )

    except Exception as exc:
        results.append({
            "ticker": ticker,
            "date": "",
            "close": float("nan"),
            "EMA_50": float("nan"),
            "RSI_14": float("nan"),
            "MACD": float("nan"),
            "MACD_Signal": float("nan"),
            "signal": "ERROR",
            "reason": str(exc),
        })
        print(f"{ticker}: ERROR — {exc}")


report = pd.DataFrame(results)

timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
csv_report = reports_dir / f"mahi_signals_{timestamp}.csv"
md_report = reports_dir / f"mahi_signals_{timestamp}.md"

report.to_csv(csv_report, index=False)

with open(md_report, "w", encoding="utf-8") as file:
    file.write("# Mahi's 12-Stock Trading Signal Report\n\n")
    file.write(f"- Generated at: {timestamp}\n")
    file.write("- Strategy: Close above EMA 50, MACD above signal, RSI 50–70\n")
    file.write("- Execution: No orders placed\n")
    file.write("- Note: These are experimental signals, not validated trading advice.\n\n")
    file.write(report.to_markdown(index=False))
    file.write("\n")

print("\nSignal generation finished.")
print(f"CSV report: {csv_report.relative_to(project_root)}")
print(f"Markdown report: {md_report.relative_to(project_root)}")
print("\nNo orders were placed.")
