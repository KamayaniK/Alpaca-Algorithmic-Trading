
from pathlib import Path

import pandas as pd


def calculate_indicators(
    df: pd.DataFrame,
    spy_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calculate technical indicators and optional SPY-relative strength."""

    result = df.copy()
    result.columns = [str(c).strip().lower() for c in result.columns]

    required = ["open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in result.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result = result.dropna(subset=required).copy()
    if result.empty:
        raise ValueError("No valid OHLCV rows found.")

    if (result[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("Prices must be positive.")
    if (result["volume"] < 0).any():
        raise ValueError("Volume cannot be negative.")

    close = result["close"]
    high = result["high"]
    low = result["low"]

    # Trend
    result["EMA_20"] = close.ewm(
        span=20, adjust=False, min_periods=20
    ).mean()
    result["EMA_50"] = close.ewm(
        span=50, adjust=False, min_periods=50
    ).mean()

    # RSI (14)
    change = close.diff()
    gains = change.clip(lower=0)
    losses = -change.clip(upper=0)
    avg_gain = gains.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()
    avg_loss = losses.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()

    rs = avg_gain / avg_loss
    result["RSI_14"] = 100 - (100 / (1 + rs))
    result.loc[(avg_loss == 0) & (avg_gain > 0), "RSI_14"] = 100
    result.loc[(avg_loss == 0) & (avg_gain == 0), "RSI_14"] = 50

    # MACD (12, 26, 9)
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    result["MACD"] = ema12 - ema26
    result["MACD_Signal"] = result["MACD"].ewm(
        span=9, adjust=False, min_periods=9
    ).mean()
    result["MACD_Histogram"] = result["MACD"] - result["MACD_Signal"]
    # ATR (14)
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

    # ADX (14)
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where(
        (up_move > down_move) & (up_move > 0), 0.0
    )
    minus_dm = down_move.where(
        (down_move > up_move) & (down_move > 0), 0.0
    )
    atr_for_adx = true_range.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean().replace(0, float("nan"))

    plus_di = 100 * plus_dm.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean() / atr_for_adx
    minus_di = 100 * minus_dm.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean() / atr_for_adx

    di_sum = (plus_di + minus_di).replace(0, float("nan"))
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    result["ADX_14"] = dx.ewm(
        alpha=1 / 14, adjust=False, min_periods=14
    ).mean()
    result["PLUS_DI_14"] = plus_di
    result["MINUS_DI_14"] = minus_di
    # Volume confirmation
    result["Volume_SMA_5"] = result["volume"].rolling(
        5, min_periods=5
    ).mean()
    result["Volume_SMA_20"] = result["volume"].rolling(
        20, min_periods=20
    ).mean()
    result["Volume_Ratio_5_20"] = (
        result["Volume_SMA_5"] / result["Volume_SMA_20"].replace(0, float("nan"))
    )
    result["Price_Change_1D"] = close.pct_change()

    # Relative strength versus SPY, aligned by date when supplied.
    result["RS_20D_vs_SPY"] = float("nan")
    if spy_df is not None:
        spy = spy_df.copy()
        spy.columns = [str(c).strip().lower() for c in spy.columns]
        if "timestamp" not in result.columns or "timestamp" not in spy.columns:
            raise ValueError("Stock and SPY data must both have timestamp columns.")
        if "close" not in spy.columns:
            raise ValueError("SPY data must contain a close column.")

        result["_date"] = pd.to_datetime(
            result["timestamp"], utc=True, errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        spy["_date"] = pd.to_datetime(
            spy["timestamp"], utc=True, errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        spy["close"] = pd.to_numeric(spy["close"], errors="coerce")
        spy = spy.dropna(subset=["_date", "close"]).drop_duplicates(
            "_date", keep="last"
        ).set_index("_date")

        spy_return = spy["close"].pct_change(20)
        stock_return = close.pct_change(20)
        stock_dates = result["_date"]
        benchmark_returns = stock_dates.map(spy_return)
        result["RS_20D_vs_SPY"] = stock_return.to_numpy() - benchmark_returns.to_numpy()
        result.drop(columns=["_date"], inplace=True)

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
    root = Path(__file__).resolve().parent.parent
    stock_data = pd.read_csv(root / f"{ticker}_daily_ohlcv_100.csv")
    spy_data = pd.read_csv(root / "SPY_daily_ohlcv_100.csv")
    result = calculate_indicators(stock_data, spy_data)

    columns = [
        "timestamp", "close", "EMA_20", "EMA_50", "RSI_14",
        "MACD", "MACD_Signal", "ATR_14", "ADX_14",
        "Volume_Ratio_5_20", "RS_20D_vs_SPY",
    ]
    print(result[[c for c in columns if c in result.columns]].tail())
