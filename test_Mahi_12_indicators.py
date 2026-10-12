
from pathlib import Path
import pandas as pd

from indicators.technical_indicators import calculate_indicators

MY_STOCKS = [
    "SNDK", "AMD", "APP", "MRNA",
    "GOOGL", "AMZN", "JPM", "LLY",
    "META", "XOM", "PEP", "ABT",
]

project_root = Path(__file__).resolve().parent

print("Testing technical indicators for Mahi's 12 stocks\n")

success_count = 0

for ticker in MY_STOCKS:
    csv_path = project_root / f"{ticker}_daily_ohlcv_100.csv"

    try:
        data = pd.read_csv(csv_path)
        result = calculate_indicators(data)

        latest = result.iloc[-1]

        indicator_columns = [
            "EMA_20", "EMA_50", "RSI_14",
            "MACD", "MACD_Signal", "ATR_14",
        ]

        missing = [
            col for col in indicator_columns
            if col not in result.columns or pd.isna(latest[col])
        ]

        if missing:
            print(
                f"{ticker}: CHECK - {len(data)} rows; "
                f"latest values missing: {', '.join(missing)}"
            )
        else:
            print(
                f"{ticker}: OK - {len(data)} rows; "
                f"close={latest['close']:.2f}; "
                f"RSI={latest['RSI_14']:.2f}"
            )
            success_count += 1

    except Exception as exc:
        print(f"{ticker}: FAILED - {exc}")

print(f"\nIndicators complete: {success_count}/{len(MY_STOCKS)}")
