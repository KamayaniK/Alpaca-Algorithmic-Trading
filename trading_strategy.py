
"""Deterministic trading signals for the Alpaca algorithmic trading project.

This module generates research signals only. It does not place orders.
"""

from typing import Any


REQUIRED_FIELDS = (
    "close",
    "EMA_20",
    "EMA_50",
    "RSI_14",
    "MACD",
    "MACD_Signal",
    "ATR_14",
)


def generate_signal(
    indicators: dict[str, Any],
    *,
    max_atr_pct: float = 5.0,
) -> dict[str, Any]:
    """Return BUY, SELL, or HOLD using explicit indicator rules.

    Expected input: the latest indicator row as a dictionary.
    max_atr_pct is the maximum permitted ATR as a percentage of price.
    """

    missing = [
        field
        for field in REQUIRED_FIELDS
        if indicators.get(field) is None
    ]

    if missing:
        return {
            "signal": "HOLD",
            "reason": "Missing required indicator values.",
            "risk_flags": [f"Missing fields: {', '.join(missing)}"],
            "evidence": {},
        }

    try:
        values = {
            field: float(indicators[field])
            for field in REQUIRED_FIELDS
        }
    except (TypeError, ValueError):
        return {
            "signal": "HOLD",
            "reason": "Indicator values must be numeric.",
            "risk_flags": ["Invalid indicator values"],
            "evidence": {},
        }

    if not all(
        __import__("math").isfinite(value)
        for value in values.values()
    ):
        return {
            "signal": "HOLD",
            "reason": "Indicator values contain NaN or infinity.",
            "risk_flags": ["Non-finite indicator values"],
            "evidence": {},
        }

    close = values["close"]
    atr = values["ATR_14"]

    if close <= 0 or atr < 0:
        return {
            "signal": "HOLD",
            "reason": "Invalid price or ATR.",
            "risk_flags": ["Invalid market values"],
            "evidence": values,
        }

    atr_pct = atr / close * 100
    evidence = {**values, "ATR_pct": round(atr_pct, 4)}
    risk_flags = []

    if atr_pct > max_atr_pct:
        return {
            "signal": "HOLD",
            "reason": "Volatility exceeds the configured threshold.",
            "risk_flags": ["High volatility"],
            "evidence": evidence,
        }

    bullish_trend = close > values["EMA_20"] > values["EMA_50"]
    bearish_trend = close < values["EMA_20"] < values["EMA_50"]
    bullish_momentum = values["MACD"] > values["MACD_Signal"]
    bearish_momentum = values["MACD"] < values["MACD_Signal"]

    # Avoid chasing an overbought move or selling an oversold move.
    if bullish_trend and bullish_momentum and 50 <= values["RSI_14"] < 70:
        signal = "BUY"
        reason = "Bullish trend and MACD confirmation; RSI is below 70."
    elif bearish_trend and bearish_momentum and 30 < values["RSI_14"] <= 50:
        signal = "SELL"
        reason = "Bearish trend and MACD confirmation; RSI is above 30."
    else:
        signal = "HOLD"
        reason = "Trend, momentum, and RSI do not align."

    return {
        "signal": signal,
        "reason": reason,
        "risk_flags": risk_flags,
        "evidence": evidence,
    }
