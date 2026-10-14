from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import pandas as pd
from mcp.server.fastmcp import FastMCP
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY
from indicators.technical_indicators import calculate_indicators


ROOT = Path(__file__).resolve().parent

ALLOWED_TICKERS = {
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
}

mcp = FastMCP("technical-indicators-market-data")

data_client = StockHistoricalDataClient(
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
)


def validate_ticker(ticker: str) -> str:
    """Normalize and validate a ticker against the project universe."""
    if not isinstance(ticker, str):
        raise ValueError("Ticker must be a string.")

    ticker = ticker.strip().upper()

    if ticker not in ALLOWED_TICKERS:
        raise ValueError(
            f"Unsupported ticker {ticker!r}. "
            "Use one of the project's 36 allowed stocks."
        )

    return ticker


def json_safe(value):
    """Convert pandas/numpy values to JSON-safe Python values."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    return value


def fetch_daily_bars(
    tickers: list[str],
    days: int = 150,
) -> dict[str, pd.DataFrame]:
    """
    Fetch daily IEX OHLCV bars for multiple tickers in one Alpaca request.

    Returns a mapping from ticker to its DataFrame.
    """
    if not isinstance(tickers, list) or not tickers:
        raise ValueError("tickers must be a non-empty list.")

    if not 1 <= days <= 220:
        raise ValueError("days must be between 1 and 220.")

    symbols = list(dict.fromkeys(validate_ticker(t) for t in tickers))

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        limit=10000,
        feed="iex",
    )

    response = data_client.get_stock_bars(request)
    bars = response.df

    results = {}

    for ticker in symbols:
        try:
            if bars.empty:
                results[ticker] = pd.DataFrame()
                continue

            # Alpaca's multi-symbol response normally has a symbol index level.
            if isinstance(bars.index, pd.MultiIndex):
                available_symbols = bars.index.get_level_values("symbol")
                if ticker not in available_symbols:
                    results[ticker] = pd.DataFrame()
                    continue

                frame = bars.xs(ticker, level="symbol").copy()
            else:
                # Single-symbol responses may not have a symbol index.
                if len(symbols) != 1:
                    results[ticker] = pd.DataFrame()
                    continue
                frame = bars.copy()

            frame = frame.reset_index()
            frame.columns = [
                str(column).strip().lower()
                for column in frame.columns
            ]

            required = ["open", "high", "low", "close", "volume"]
            missing = [col for col in required if col not in frame.columns]

            if missing:
                raise ValueError(
                    f"{ticker}: missing OHLCV columns {missing}"
                )

            frame = frame.sort_values(
                "timestamp" if "timestamp" in frame.columns
                else frame.columns[0]
            ).reset_index(drop=True)

            results[ticker] = frame

        except (KeyError, ValueError) as exc:
            raise ValueError(
                f"Could not process Alpaca bars for {ticker}: {exc}"
            ) from exc

    return results


def fetch_spy_bars(days: int = 150) -> pd.DataFrame:
    """Fetch SPY benchmark bars without adding SPY to the allowed stock universe."""
    if not 1 <= days <= 220:
        raise ValueError("days must be between 1 and 220.")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    request = StockBarsRequest(
        symbol_or_symbols=["SPY"],
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        limit=10000,
        feed="iex",
    )

    response = data_client.get_stock_bars(request)
    bars = response.df

    if bars.empty:
        raise ValueError("No SPY benchmark bars returned by Alpaca.")

    if isinstance(bars.index, pd.MultiIndex):
        if "SPY" not in bars.index.get_level_values("symbol"):
            raise ValueError("SPY was missing from Alpaca's response.")
        frame = bars.xs("SPY", level="symbol").copy()
    else:
        frame = bars.copy()

    frame = frame.reset_index()
    frame.columns = [str(column).strip().lower() for column in frame.columns]

    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"SPY benchmark data is missing columns: {missing}")

    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"])
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    if frame.empty:
        raise ValueError("SPY benchmark data contains no valid timestamps.")

    return frame


def analyze_frame(
    ticker: str,
    frame: pd.DataFrame,
    spy_frame: pd.DataFrame | None = None,
) -> dict:
    """Calculate indicators and include the previous MACD histogram."""
    if frame.empty:
        return {
            "ticker": ticker,
            "error": "No market data returned for this ticker.",
        }

    indicators = calculate_indicators(frame, spy_df=spy_frame)

    if indicators.empty:
        return {
            "ticker": ticker,
            "error": "No indicator rows produced.",
        }

    # Use the last two rows with valid MACD histogram values.
    valid_histograms = indicators.loc[
        pd.to_numeric(
            indicators["MACD_Histogram"], errors="coerce"
        ).map(lambda value: pd.notna(value) and math.isfinite(float(value)))
    ]

    latest = indicators.iloc[-1].to_dict()

    previous_histogram = None
    if len(valid_histograms) >= 2 and valid_histograms.index[-1] == indicators.index[-1]:
        previous_histogram = valid_histograms.iloc[-2]["MACD_Histogram"]

    latest["MACD_Histogram_Previous"] = json_safe(previous_histogram)

    return {
        "ticker": ticker,
        "bars_used": len(indicators),
        "latest_indicators": json_safe(latest),
    }


@mcp.tool()
def get_account_summary() -> str:
    """
    Return basic account status using a read-only paper-account request.

    This tool does not submit, cancel, or modify orders.
    """
    import requests

    response = requests.get(
        "https://paper-api.alpaca.markets/v2/account",
        headers={
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
        },
        timeout=20,
    )
    response.raise_for_status()
    account = response.json()

    return json.dumps({
        "status": account.get("status"),
        "trading_blocked": account.get("trading_blocked"),
        "paper_account": True,
        "currency": account.get("currency"),
    }, allow_nan=False)


@mcp.tool()
def get_stock_bars(tickers: list[str], days: int = 30) -> str:
    """
    Fetch recent daily OHLCV data for multiple allowed tickers in one request.

    Returns up to the most recent 10 bars per ticker.
    """
    try:
        frames = fetch_daily_bars(tickers, days)

        result = {}

        for ticker, frame in frames.items():
            if frame.empty:
                result[ticker] = {
                    "error": "No bars returned for this ticker."
                }
                continue

            result[ticker] = {
                "bars_returned": min(10, len(frame)),
                "bars": json_safe(
                    frame.tail(10).to_dict(orient="records")
                ),
            }

        return json.dumps(result, allow_nan=False)

    except Exception as exc:
        return json.dumps({
            "error": f"{type(exc).__name__}: {exc}"
        })


@mcp.tool()
def calculate_stock_indicators(ticker: str) -> str:
    """
    Fetch historical bars from Alpaca and calculate indicators in memory.

    No CSV files are required. This tool does not place orders.
    """
    try:
        ticker = validate_ticker(ticker)
        frames = fetch_daily_bars([ticker], days=150)
        spy_frame = fetch_spy_bars(days=150)
        result = analyze_frame(ticker, frames[ticker], spy_frame=spy_frame)

        return json.dumps(result, allow_nan=False)

    except Exception as exc:
        return json.dumps({
            "ticker": ticker if isinstance(ticker, str) else None,
            "error": f"{type(exc).__name__}: {exc}",
        })



@mcp.tool()
def calculate_multiple_stock_indicators(
    tickers: list[str],
    days: int = 150,
) -> str:
    """
    Fetch OHLCV for multiple stocks and calculate indicators locally.
    No orders are submitted.
    """
    try:
        frames = fetch_daily_bars(tickers, days)
        spy_frame = fetch_spy_bars(days)
        results = {}

        for ticker, frame in frames.items():
            try:
                results[ticker] = analyze_frame(
                    ticker, frame, spy_frame=spy_frame
                )
            except Exception as exc:
                results[ticker] = {
                    "ticker": ticker,
                    "error": f"{type(exc).__name__}: {exc}",
                }

        return json.dumps(results, allow_nan=False)

    except Exception as exc:
        return json.dumps({
            "error": f"{type(exc).__name__}: {exc}"
        })



@mcp.tool()
def validate_local_stock_data(ticker: str) -> str:
    """
    Validate a local OHLCV CSV if one exists.

    This optional legacy utility does not affect the live-data pipeline.
    """
    try:
        ticker = validate_ticker(ticker)

        candidates = [
            ROOT / f"{ticker}_daily_ohlcv_100.csv",
            ROOT / f"{ticker}_daily_ohlcv.csv",
        ]

        csv_path = next(
            (path for path in candidates if path.is_file()),
            None,
        )

        if csv_path is None:
            return json.dumps({
                "ticker": ticker,
                "valid": False,
                "issues": ["No local OHLCV CSV found; this is optional."],
            })

        df = pd.read_csv(csv_path)
        df.columns = [str(column).strip().lower() for column in df.columns]

        required = {
            "timestamp", "open", "high", "low", "close", "volume"
        }
        missing = sorted(required - set(df.columns))
        issues = []

        if missing:
            issues.append(f"Missing columns: {missing}")
        else:
            df["timestamp"] = pd.to_datetime(
                df["timestamp"], utc=True, errors="coerce"
            )

            for column in ["open", "high", "low", "close", "volume"]:
                df[column] = pd.to_numeric(
                    df[column], errors="coerce"
                )

            if df[list(required)].isna().any().any():
                issues.append("Missing or invalid OHLCV values.")

            if df["timestamp"].duplicated().any():
                issues.append("Duplicate timestamps.")

            prices = df[["open", "high", "low", "close"]]

            if (prices <= 0).any().any():
                issues.append("Non-positive prices.")

            if (df["volume"] < 0).any():
                issues.append("Negative volume.")

            if (df["high"] < prices[["open", "low", "close"]].max(axis=1)).any():
                issues.append("High is below another OHLC price.")

            if (df["low"] > prices[["open", "high", "close"]].min(axis=1)).any():
                issues.append("Low is above another OHLC price.")

        return json.dumps({
            "ticker": ticker,
            "rows": len(df),
            "latest_timestamp": (
                str(df["timestamp"].max())
                if "timestamp" in df.columns else None
            ),
            "valid": not issues,
            "issues": issues,
        }, allow_nan=False)

    except Exception as exc:
        return json.dumps({
            "ticker": ticker if isinstance(ticker, str) else None,
            "valid": False,
            "issues": [f"{type(exc).__name__}: {exc}"],
        })


if __name__ == "__main__":
    mcp.run(transport="stdio")
