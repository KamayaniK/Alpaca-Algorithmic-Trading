"""Read-only, per-member portfolio validation. Never submits orders."""

from __future__ import annotations

from math import isfinite
from typing import Mapping

from portfolio_risk import (
    ALLOWED_TICKERS,
    AI_HARDWARE_TICKERS,
    TECHNOLOGY_TICKERS,
    RiskResult,
    validate_portfolio,
)


TEAM_TICKERS = {
    "Mahi": {
        "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
        "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    },
    "Ashima": {
        "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
        "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    },
    "Kamayani": {
        "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
        "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
    },
}


def validate_member_portfolio(
    member: str,
    positions: Mapping[str, float],
    *,
    account_equity: float,
    account_cash: float,
) -> RiskResult:
    """Validate actual long position market values for one team member.

    Inputs must come from a trusted read-only account snapshot.
    This function never connects to Alpaca and never submits orders.
    """
    if member not in TEAM_TICKERS:
        return RiskResult(False, [f"Unknown team member: {member!r}."])

    if not isinstance(positions, Mapping):
        return RiskResult(False, ["Positions must be a ticker-to-value mapping."])

    for name, value in (("account equity", account_equity),
                        ("account cash", account_cash)):
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not isfinite(value) or value < 0):
            return RiskResult(False, [f"{name.capitalize()} must be finite and non-negative."])

    errors = []
    for raw_ticker in positions:
        ticker = raw_ticker.strip().upper() if isinstance(raw_ticker, str) else ""
        if ticker not in TEAM_TICKERS[member]:
            errors.append(
                f"{ticker or raw_ticker!r}: not assigned to {member}'s portfolio."
            )
        elif ticker not in ALLOWED_TICKERS:
            errors.append(f"{ticker}: outside the approved ticker universe.")

    if errors:
        return RiskResult(False, errors)

    # Check position/exposure limits using observed equity as the account value.
    result = validate_portfolio(
        positions,
        account_value=float(account_equity),
        technology_tickers=TECHNOLOGY_TICKERS,
        ai_hardware_tickers=AI_HARDWARE_TICKERS,
    )

    # Compare observed cash with the cash implied by equity minus positions.
    # This catches inconsistent snapshots rather than silently trusting either.
    invested = sum(float(v) for v in positions.values())
    implied_cash = float(account_equity) - invested
    tolerance = 1.00
    snapshot_errors = []

    if abs(float(account_cash) - implied_cash) > tolerance:
        snapshot_errors.append(
            "Account cash does not reconcile with equity minus supplied position values; "
            "verify the account snapshot and market-value inputs."
        )

    if float(account_cash) < 5000.00:
        snapshot_errors.append("Actual account cash is below the $5,000 minimum reserve.")

    result.errors.extend(snapshot_errors)
    result.passed = not result.errors
    result.metrics["observed_account_cash"] = round(float(account_cash), 2)
    result.metrics["implied_cash_from_positions"] = round(implied_cash, 2)
    result.metrics["account_equity"] = round(float(account_equity), 2)
    result.metrics["execution_enabled"] = 0.0
    return result
