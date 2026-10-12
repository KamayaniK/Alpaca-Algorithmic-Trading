
"""Portfolio-level risk checks for the 36-stock paper-trading project.

Analysis only: this module never submits orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Mapping


ACCOUNT_VALUE = 100_000.00
MAX_PLANNED_INVESTMENT = 95_000.00
MIN_CASH_RESERVE = 5_000.00
MAX_POSITION_VALUE = 13_000.00

MAX_TECHNOLOGY_EXPOSURE = MAX_PLANNED_INVESTMENT * 0.35
MAX_AI_HARDWARE_EXPOSURE = MAX_PLANNED_INVESTMENT * 0.25

# Explicit initial classifications for this project's 36-stock universe.
# Review these mappings with your team before relying on them for decisions.
TECHNOLOGY_TICKERS = {
    "SNDK", "AMD", "APP", "GOOGL", "AMZN", "META",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "PLTR",
    "LITE", "AAPL", "NFLX", "HOOD", "COIN",
}

AI_HARDWARE_TICKERS = {
    "SNDK", "AMD", "SMCI", "MU", "MRVL", "WDC", "LITE",
}

ALLOWED_TICKERS = {
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
}


@dataclass
class RiskResult:
    """Result of a portfolio risk validation."""

    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "errors": self.errors.copy(),
            "warnings": self.warnings.copy(),
            "metrics": self.metrics.copy(),
            "execution_enabled": False,
        }


def validate_portfolio(
    positions: Mapping[str, float],
    *,
    account_value: float = ACCOUNT_VALUE,
    technology_tickers: set[str] | frozenset[str] = TECHNOLOGY_TICKERS,
    ai_hardware_tickers: set[str] | frozenset[str] = AI_HARDWARE_TICKERS,
) -> RiskResult:
    """Validate proposed long-only position values, in USD.

    `positions` maps ticker symbols to proposed position market values.
    Zero-value positions are allowed; negative values are prohibited.
    Exposure limits use the fixed $95,000 planned-investment budget.
    """

    errors: list[str] = []
    warnings: list[str] = []
    normalized: dict[str, float] = {}

    if not isinstance(account_value, (int, float)) or isinstance(account_value, bool):
        return RiskResult(False, ["Account value must be numeric."])

    if not isfinite(account_value) or account_value <= 0:
        return RiskResult(False, ["Account value must be finite and positive."])

    for raw_ticker, raw_value in positions.items():
        if not isinstance(raw_ticker, str) or not raw_ticker.strip():
            errors.append(f"Invalid ticker: {raw_ticker!r}")
            continue

        ticker = raw_ticker.strip().upper()

        if ticker not in ALLOWED_TICKERS:
            errors.append(f"{ticker}: ticker is outside the approved 36-stock universe.")
            continue

        if ticker in normalized:
            errors.append(f"{ticker}: duplicate ticker after normalization.")
            continue

        if (
            not isinstance(raw_value, (int, float))
            or isinstance(raw_value, bool)
            or not isfinite(raw_value)
        ):
            errors.append(f"{ticker}: position value must be a finite number.")
            continue

        value = float(raw_value)

        if value < 0:
            errors.append(
                f"{ticker}: negative position value is prohibited; "
                "short selling is not allowed."
            )
            continue

        normalized[ticker] = value

        if value > MAX_POSITION_VALUE:
            errors.append(
                f"{ticker}: ${value:,.2f} exceeds the "
                f"${MAX_POSITION_VALUE:,.2f} single-position cap."
            )

    total_invested = sum(normalized.values())
    cash_remaining = account_value - total_invested

    technology_exposure = sum(
        value for ticker, value in normalized.items()
        if ticker in technology_tickers
    )
    ai_hardware_exposure = sum(
        value for ticker, value in normalized.items()
        if ticker in ai_hardware_tickers
    )

    if total_invested > MAX_PLANNED_INVESTMENT:
        errors.append(
            f"Total investment ${total_invested:,.2f} exceeds the "
            f"${MAX_PLANNED_INVESTMENT:,.2f} planned-investment budget."
        )

    if cash_remaining < MIN_CASH_RESERVE:
        errors.append(
            f"Remaining cash ${cash_remaining:,.2f} is below the "
            f"${MIN_CASH_RESERVE:,.2f} required reserve."
        )

    if technology_exposure > MAX_TECHNOLOGY_EXPOSURE:
        errors.append(
            f"Technology exposure ${technology_exposure:,.2f} exceeds "
            f"the ${MAX_TECHNOLOGY_EXPOSURE:,.2f} limit."
        )

    if ai_hardware_exposure > MAX_AI_HARDWARE_EXPOSURE:
        errors.append(
            f"AI-hardware exposure ${ai_hardware_exposure:,.2f} exceeds "
            f"the ${MAX_AI_HARDWARE_EXPOSURE:,.2f} limit."
        )

    if not normalized:
        warnings.append("No valid positions were supplied.")

    metrics = {
        "account_value": float(account_value),
        "total_invested": round(total_invested, 2),
        "cash_remaining": round(cash_remaining, 2),
        "technology_exposure": round(technology_exposure, 2),
        "technology_limit": MAX_TECHNOLOGY_EXPOSURE,
        "ai_hardware_exposure": round(ai_hardware_exposure, 2),
        "ai_hardware_limit": MAX_AI_HARDWARE_EXPOSURE,
        "max_single_position": MAX_POSITION_VALUE,
    }

    return RiskResult(
        passed=not errors,
        errors=errors,
        warnings=warnings,
        metrics=metrics,
    )


def validate_signals(signals: Mapping[str, str]) -> RiskResult:
    """Reject unsupported tickers/signals and any short-selling instruction.

    SELL means review/reduce an existing long position; it is not an
    instruction to open a short position.
    """

    errors: list[str] = []

    for raw_ticker, raw_signal in signals.items():
        ticker = raw_ticker.strip().upper() if isinstance(raw_ticker, str) else ""

        if ticker not in ALLOWED_TICKERS:
            errors.append(f"{raw_ticker!r}: ticker is outside the approved universe.")
            continue

        if not isinstance(raw_signal, str):
            errors.append(f"{ticker}: signal must be a string.")
            continue

        signal = raw_signal.strip().upper()

        if signal not in {"BUY", "HOLD", "SELL"}:
            errors.append(
                f"{ticker}: unsupported signal {raw_signal!r}; "
                "short-selling or unknown instructions are prohibited."
            )

    return RiskResult(
        passed=not errors,
        errors=errors,
        warnings=[
            "SELL signals require checking an existing long position; "
            "this function does not submit orders."
        ],
    )
