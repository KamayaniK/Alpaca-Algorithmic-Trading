
from pathlib import Path

import pandas as pd


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate EMA, RSI, MACD and ATR from OHLCV data."""

    # Normalize column names, for example Open -> open
    result = df.copy()
    result.columns = [
        str(column).strip().lower() for column in result.columns
    ]

    required = ["open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in result.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Convert OHLCV columns to numeric values
    for column in required:
        result[column] = pd.to_numeric(
            result[column], errors="coerce"
        )

    # Remove rows without valid OHLCV values
    result = result.dropna(subset=required).copy()

    if result.empty:
        raise ValueError("No valid OHLCV rows found in the input data.")

    close = result["close"]
    high = result["high"]
    low = result["low"]

    # 1. Exponential Moving Averages
    result["EMA_20"] = close.ewm(
        span=20, adjust=False, min_periods=20
    ).mean()

    result["EMA_50"] = close.ewm(
        span=50, adjust=False, min_periods=50
    ).mean()

    # 2. Relative Strength Index (RSI), 14 periods
    change = close.diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)

    avg_gain = gains.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    avg_loss = losses.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    relative_strength = avg_gain / avg_loss
    result["RSI_14"] = 100 - (
        100 / (1 + relative_strength)
    )

    # Handle zero-loss cases
    result.loc[
        (avg_loss == 0) & (avg_gain > 0), "RSI_14"
    ] = 100

    result.loc[
        (avg_loss == 0) & (avg_gain == 0), "RSI_14"
    ] = 50

    # 3. MACD and its signal line
    ema_12 = close.ewm(
        span=12, adjust=False, min_periods=12
    ).mean()

    ema_26 = close.ewm(
        span=26, adjust=False, min_periods=26
    ).mean()

    result["MACD"] = ema_12 - ema_26

    result["MACD_Signal"] = result["MACD"].ewm(
        span=9, adjust=False, min_periods=9
    ).mean()

    # 4. Average True Range (ATR), 14 periods
    previous_close = close.shift(1)

    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    result["ATR_14"] = true_range.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    return result


def load_stock_csv(ticker: str) -> pd.DataFrame:
    """Load a ticker's daily OHLCV CSV from the project root."""

    ticker = ticker.strip().upper()

    if not ticker.isalnum():
        raise ValueError("Ticker must contain only letters and numbers.")

    project_root = Path(__file__).resolve().parent.parent
    csv_path = project_root / f"{ticker}_daily_ohlcv.csv"

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    return pd.read_csv(csv_path)


if __name__ == "__main__":
    ticker = "AMD"

    from pathlib import Path
    csv_path = Path(__file__).resolve().parent.parent / "AMD_daily_ohlcv_100.csv"
    stock_data = pd.read_csv(csv_path)
    result = calculate_indicators(stock_data)

    columns_to_show = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "EMA_20",
        "EMA_50",
        "RSI_14",
        "MACD",
        "MACD_Signal",
        "ATR_14",
    ]

    columns_to_show = [
        column for column in columns_to_show
        if column in result.columns
    ]

    print(f"\nTicker tested: {ticker}")
    print(f"Valid OHLCV rows: {len(result)}")
    print("\nMost recent indicator values:")
    print(result[columns_to_show].tail(5).to_string(index=False))
    print("\nIndicator test completed.")
