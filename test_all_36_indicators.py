
from pathlib import Path
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

ROOT = Path(__file__).resolve().parent
successful = []
failed = []

for ticker in TICKERS:
    file_path = ROOT / f"{ticker}_daily_ohlcv_100.csv"

    try:
        if not file_path.exists():
            raise FileNotFoundError(f"Missing file: {file_path.name}")

        df = pd.read_csv(file_path)
        result = calculate_indicators(df)

        if result.empty:
            raise ValueError("Indicator calculation returned no rows")

        latest = result.iloc[-1]
        successful.append(ticker)

        print(
            f"PASS {ticker}: "
            f"rows={len(result)}, "
            f"latest_close={latest['close']:.2f}, "
            f"RSI={latest['RSI_14']:.2f}"
        )

    except Exception as error:
        failed.append((ticker, str(error)))
        print(f"FAIL {ticker}: {error}")

print("\n========== SUMMARY ==========")
print(f"Indicator success: {len(successful)} of {len(TICKERS)}")
print(f"Failed: {len(failed)}")

if failed:
    for ticker, error in failed:
        print(f"  {ticker}: {error}")
else:
    print("All 36 stocks passed indicator calculation.")
