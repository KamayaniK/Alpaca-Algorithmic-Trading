
from pathlib import Path
import json

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
    ticker = ticker.strip().upper()
    if ticker not in ALLOWED_TICKERS:
        raise ValueError(
            f"Unsupported ticker {ticker}. Use one of the project's 36 stocks."
        )
    return ticker


def load_local_history(ticker: str) -> pd.DataFrame:
    """Prefer longer history; fall back to the original CSV."""
    candidates = [
        ROOT / f"{ticker}_daily_ohlcv_100.csv",
        ROOT / f"{ticker}_daily_ohlcv.csv",
    ]

    for path in candidates:
        if path.exists():
            df = pd.read_csv(path)
            df.columns = [str(c).lower() for c in df.columns]
            return df

    raise FileNotFoundError(f"No local OHLCV CSV found for {ticker}.")


@mcp.tool()
def get_account_summary() -> str:
    """Return basic Alpaca paper-account status. Does not place orders."""
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
    })


@mcp.tool()
def get_stock_bars(tickers: list[str], days: int = 30) -> str:
    """Fetch daily OHLCV bars from Alpaca IEX for one or more project tickers."""
    if not 1 <= days <= 220:
        raise ValueError("days must be between 1 and 220.")

    symbols = list(dict.fromkeys(validate_ticker(t) for t in tickers))
    request = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        start=pd.Timestamp.now(tz="UTC").to_pydatetime()
        - pd.Timedelta(days=days),
        end=pd.Timestamp.now(tz="UTC").to_pydatetime(),
        limit=1000,
        feed="iex",
    )

    result = {}
    try:
        bars = data_client.get_stock_bars(request).df
    except Exception as exc:
        return json.dumps({"error": f"Alpaca data request failed: {exc}"})

    for ticker in symbols:
        try:
            frame = bars.xs(ticker, level="symbol").reset_index()
            frame.columns = [str(c).lower() for c in frame.columns]
            result[ticker] = frame.tail(10).to_dict(orient="records")
        except (KeyError, ValueError):
            result[ticker] = {"error": "No bars returned for this ticker."}

    return json.dumps(result, default=str)


@mcp.tool()
def calculate_stock_indicators(ticker: str) -> str:
    """Calculate indicators from the most recent locally saved OHLCV CSV."""
    ticker = validate_ticker(ticker)
    df = load_local_history(ticker)
    indicators = calculate_indicators(df)

    if indicators.empty:
        return json.dumps({"ticker": ticker, "error": "No indicator rows produced."})

    latest = indicators.tail(1).copy()
    latest = latest.where(pd.notna(latest), None)
    return json.dumps({
        "ticker": ticker,
        "latest_indicators": latest.to_dict(orient="records")[0],
    }, default=str)


@mcp.tool()
def validate_local_stock_data(ticker: str) -> str:
    """Check local OHLCV CSV columns, missing values, duplicate dates and prices."""
    ticker = validate_ticker(ticker)
    df = load_local_history(ticker)

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing_columns = sorted(required - set(df.columns))
    issues = []

    if missing_columns:
        issues.append(f"Missing columns: {missing_columns}")
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        if df[list(required)].isna().any().any():
            issues.append("Missing or invalid OHLCV values.")
        if df["timestamp"].duplicated().any():
            issues.append("Duplicate timestamps.")
        if (df[["open", "high", "low", "close"]] <= 0).any().any():
            issues.append("Non-positive prices.")
        if (df["volume"] < 0).any():
            issues.append("Negative volume.")
        if (df["high"] < df[["open", "low", "close"]].max(axis=1)).any():
            issues.append("High is below another OHLC price.")
        if (df["low"] > df[["open", "high", "close"]].min(axis=1)).any():
            issues.append("Low is above another OHLC price.")

    return json.dumps({
        "ticker": ticker,
        "rows": len(df),
        "latest_timestamp": str(df["timestamp"].max()) if "timestamp" in df else None,
        "valid": not issues,
        "issues": issues,
    })


if __name__ == "__main__":
    mcp.run()
