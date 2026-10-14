
"""Deterministic weighted trading signals for the Alpaca project.

Research signals only. This module does not place, modify, or cancel orders.
"""

from math import isfinite
from typing import Any


# Assignment weights: these must sum to 1.0.
WEIGHTS = {
    "trend": 0.25,
    "macd": 0.20,
    "relative_strength": 0.20,
    "rsi": 0.15,
    "adx": 0.10,
    "volume": 0.10,
}

BUY_THRESHOLD = 0.35
SELL_THRESHOLD = -0.25


# Required for the six-factor strategy and existing volatility guard.
REQUIRED_FIELDS = (
    "close",
    "EMA_20",
    "EMA_50",
    "RSI_14",
    "MACD",
    "MACD_Signal",
    "MACD_Histogram",
    "ATR_14",
    "RS_20D_vs_SPY",
    "ADX_14",
    "PLUS_DI_14",
    "MINUS_DI_14",
    "Volume_Ratio_5_20",
    "Price_Change_1D",
)


def _hold(reason: str, risk_flags: list[str] | None = None,
          evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a consistent fail-safe HOLD result."""
    return {
        "signal": "HOLD",
        "reason": reason,
        "risk_flags": risk_flags or [],
        "evidence": evidence or {},
    }


def generate_signal(
    indicators: dict[str, Any],
    *,
    max_atr_pct: float = 5.0,
) -> dict[str, Any]:
    """Calculate a weighted research signal from the latest indicator row.

    Score range: -1.0 to +1.0.
    BUY: score >= +0.35, bullish trend confirmation, valid news check.
    SELL: score <= -0.25 (execution must separately verify a long position).
    HOLD: otherwise, including missing/invalid data.

    The caller must supply news_check_passed=True before a BUY can be
    emitted. This prevents a BUY while the assignment's severe-negative-news
    filter has not yet been connected.
    """
    if not isinstance(indicators, dict):
        return _hold("Indicator data must be a dictionary.",
                     ["Invalid indicator response"])

    missing = [
        field for field in REQUIRED_FIELDS
        if indicators.get(field) is None
    ]
    if missing:
        return _hold(
            "Missing required indicator values.",
            [f"Missing fields: {', '.join(missing)}"],
        )

    try:
        values = {
            field: float(indicators[field])
            for field in REQUIRED_FIELDS
        }
    except (TypeError, ValueError, OverflowError):
        return _hold(
            "Indicator values must be numeric.",
            ["Invalid indicator values"],
        )

    if not all(isfinite(value) for value in values.values()):
        return _hold(
            "Indicator values contain NaN or infinity.",
            ["Non-finite indicator values"],
        )

    close = values["close"]
    atr = values["ATR_14"]
    rsi = values["RSI_14"]

    if close <= 0 or atr < 0:
        return _hold(
            "Invalid price or ATR.",
            ["Invalid market values"],
            values,
        )

    if not 0 <= rsi <= 100:
        return _hold(
            "RSI is outside its valid range.",
            ["Invalid RSI"],
            values,
        )

    if values["ADX_14"] < 0 or values["ADX_14"] > 100:
        return _hold(
            "ADX is outside its valid range.",
            ["Invalid ADX"],
            values,
        )

    if values["Volume_Ratio_5_20"] < 0:
        return _hold(
            "Volume ratio cannot be negative.",
            ["Invalid volume ratio"],
            values,
        )

    atr_pct = atr / close * 100
    evidence: dict[str, Any] = {
        **values,
        "ATR_pct": round(atr_pct, 4),
    }

    # Preserve the source bar timestamp for report freshness checks.
    if indicators.get("timestamp") is not None:
        evidence["timestamp"] = str(indicators["timestamp"])
    if atr_pct > max_atr_pct:
        return _hold(
            "Volatility exceeds the configured threshold.",
            ["High volatility"],
            evidence,
        )

    # 1. Trend: require price and moving averages to agree.
    if close > values["EMA_20"] > values["EMA_50"]:
        trend_score = 1.0
    elif close < values["EMA_20"] < values["EMA_50"]:
        trend_score = -1.0
    else:
        trend_score = 0.0


    # 2. MACD: score the histogram's sign and measure its direction.
    histogram = values["MACD_Histogram"]
    previous_histogram_raw = indicators.get("MACD_Histogram_Previous")
    previous_histogram = None
    histogram_direction_confirmed = False

    if histogram > 0:
        macd_score = 1.0
    elif histogram < 0:
        macd_score = -1.0
    else:
        macd_score = 0.0

    if previous_histogram_raw is None:
        histogram_direction = "UNKNOWN"
    else:
        try:
            previous_histogram = float(previous_histogram_raw)
        except (TypeError, ValueError, OverflowError):
            previous_histogram = None
            histogram_direction = "UNKNOWN"
        else:
            histogram_direction_confirmed = isfinite(previous_histogram)
            if histogram > previous_histogram:
                histogram_direction = "RISING"
            elif histogram < previous_histogram:
                histogram_direction = "FALLING"
            else:
                histogram_direction = "UNCHANGED"

    # 3. Relative strength: 20-day stock return minus 20-day SPY return.
    relative_strength = values["RS_20D_vs_SPY"]
    if relative_strength > 0:
        relative_strength_score = 1.0
    elif relative_strength < 0:
        relative_strength_score = -1.0
    else:
        relative_strength_score = 0.0

    # 4. RSI: reward healthy momentum; penalize weakness under EMA50.
    if 50 <= rsi < 70:
        rsi_score = 1.0
    elif rsi < 40 and close < values["EMA_50"]:
        rsi_score = -1.0
    else:
        rsi_score = 0.0

    # 5. ADX confirms strength; +DI/-DI determine direction.
    adx = values["ADX_14"]
    plus_di = values["PLUS_DI_14"]
    minus_di = values["MINUS_DI_14"]

    if adx > 25 and plus_di > minus_di:
        adx_score = 1.0
    elif adx > 25 and minus_di > plus_di:
        adx_score = -1.0
    else:
        adx_score = 0.0

    # 6. Volume: only score elevated volume with matching price direction.
    volume_ratio = values["Volume_Ratio_5_20"]
    price_change = values["Price_Change_1D"]

    if volume_ratio > 1.2 and price_change > 0:
        volume_score = 1.0
    elif volume_ratio > 1.2 and price_change < 0:
        volume_score = -1.0
    else:
        volume_score = 0.0

    component_scores = {
        "trend": trend_score,
        "macd": macd_score,
        "relative_strength": relative_strength_score,
        "rsi": rsi_score,
        "adx": adx_score,
        "volume": volume_score,
    }

    weighted_score = sum(
        WEIGHTS[name] * score
        for name, score in component_scores.items()
    )


    evidence.update({
        "component_scores": component_scores,
        "weights": WEIGHTS.copy(),
        "weighted_score": round(weighted_score, 4),
        "news_check_passed": indicators.get("news_check_passed") is True,
        "MACD_Histogram_Previous": previous_histogram,
        "macd_histogram_direction": histogram_direction,
        "macd_histogram_direction_confirmed": histogram_direction_confirmed,
})

    risk_flags: list[str] = []
    if not histogram_direction_confirmed:
        risk_flags.append(
            "MACD histogram direction unavailable; only its current sign was scored."
        )

    # Assignment requires bullish trend confirmation for BUY.
    bullish_trend_confirmed = (
        close > values["EMA_20"] and close > values["EMA_50"]
    )

    if weighted_score >= BUY_THRESHOLD and bullish_trend_confirmed:
        if indicators.get("news_check_passed") is not True:
            risk_flags.append(
                "BUY blocked: severe-negative-news check is not confirmed."
            )
            return {
                "signal": "HOLD",
                "reason": (
                    f"Weighted score {weighted_score:.4f} meets the BUY "
                    "threshold, but the required news check is not confirmed."
                ),
                "risk_flags": risk_flags,
                "evidence": evidence,
            }

        if indicators.get("severe_negative_news") is True:
            return {
                "signal": "HOLD",
                "reason": "BUY blocked by severe negative news.",
                "risk_flags": ["Severe negative news"],
                "evidence": evidence,
            }

        return {
            "signal": "BUY",
            "reason": (
                f"Weighted score {weighted_score:.4f} meets the BUY "
                "threshold with bullish trend and confirmed news check."
            ),
            "risk_flags": risk_flags,
            "evidence": evidence,
        }

    if weighted_score <= SELL_THRESHOLD:
        return {
            "signal": "SELL",
            "reason": (
                f"Weighted score {weighted_score:.4f} meets the SELL threshold. "
                "Execution must verify an existing long position; short selling "
                "is prohibited."
            ),
            "risk_flags": risk_flags,
            "evidence": evidence,
        }

    return {
        "signal": "HOLD",
        "reason": (
            f"Weighted score {weighted_score:.4f} is between the "
            "BUY and SELL decision conditions."
        ),
        "risk_flags": risk_flags,
        "evidence": evidence,
    }
