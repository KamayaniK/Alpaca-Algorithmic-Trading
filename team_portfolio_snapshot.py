
"""Read-only snapshots for the three Alpaca paper accounts.

This module retrieves account and position data only.
It never submits, modifies, or cancels orders.
"""
from __future__ import annotations

from math import isfinite
from typing import Any

from alpaca.trading.client import TradingClient

from team_accounts import load_account_config
from team_portfolio_risk import validate_member_portfolio


TEAM_MEMBERS = ("Mahi", "Ashima", "Kamayani")


def fetch_member_snapshot(member: str) -> dict[str, Any]:
    """Fetch and validate one member's current paper-account snapshot."""
    config = load_account_config(member)

    if not config.paper:
        raise RuntimeError("Refusing to inspect a non-paper account.")

    client = TradingClient(
        api_key=config.api_key,
        secret_key=config.secret_key,
        paper=True,
    )

    # Read-only API calls only.
    account = client.get_account()
    positions = client.get_all_positions()

    # Validate account data before risk evaluation.
    try:
        equity = float(account.equity)
        cash = float(account.cash)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(
            "Invalid or missing account equity/cash."
        ) from exc

    if not isfinite(equity) or equity <= 0:
        raise ValueError("Account equity must be finite and positive.")

    if not isfinite(cash) or cash < 0:
        raise ValueError(
            "Account cash must be finite and non-negative."
        )

    position_values: dict[str, float] = {}
    position_details: list[dict[str, Any]] = []

    for position in positions:
        # Validate required position fields and numeric values.
        try:
            raw_ticker = position.symbol
            if not isinstance(raw_ticker, str) or not raw_ticker.strip():
                raise ValueError("Missing or invalid ticker.")

            ticker = raw_ticker.strip().upper()
            market_value = float(position.market_value)
            quantity = float(position.qty)

            raw_unrealized_pl = position.unrealized_pl
            unrealized_pl = (
                float(raw_unrealized_pl)
                if raw_unrealized_pl is not None
                else None
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(
                "Position has missing or invalid fields or numeric data."
            ) from exc

        if not isfinite(market_value) or market_value < 0:
            raise ValueError(
                f"{ticker}: market value must be finite and non-negative."
            )

        if not isfinite(quantity) or quantity <= 0:
            raise ValueError(
                f"{ticker}: quantity must be finite and positive."
            )

        if (
            unrealized_pl is not None
            and not isfinite(unrealized_pl)
        ):
            raise ValueError(
                f"{ticker}: unrealized profit/loss must be finite."
            )

        if ticker in position_values:
            raise ValueError(
                f"Duplicate position returned for {ticker}."
            )

        position_values[ticker] = market_value
        position_details.append(
            {
                "ticker": ticker,
                "quantity": str(position.qty),
                "market_value": market_value,
                "unrealized_pl": unrealized_pl,
            }
        )

    # Validate holdings, member-specific ticker assignment, and risk limits.
    risk = validate_member_portfolio(
        member,
        position_values,
        account_equity=equity,
        account_cash=cash,
    )

    return {
        "member": member,
        "mode": "PAPER",
        "access": "READ-ONLY",
        "account_status": str(account.status),
        "trading_blocked": bool(account.trading_blocked),
        "equity": equity,
        "cash": cash,
        "positions": position_details,
        "risk_passed": risk.passed,
        "risk_errors": list(risk.errors),
        "risk_warnings": list(risk.warnings),
        "risk_metrics": dict(risk.metrics),
        "execution_enabled": False,
        "order_submission_used": False,
    }


def main() -> int:
    failed = False

    for member in TEAM_MEMBERS:
        print(f"\n{'=' * 60}\n{member}\n{'=' * 60}")

        try:
            snapshot = fetch_member_snapshot(member)
        except Exception as exc:
            # Do not print credentials or client configuration.
            print(
                f"SNAPSHOT FAILED: {type(exc).__name__}: {exc}"
            )
            failed = True
            continue

        print(f"Mode: {snapshot['mode']}")
        print(f"Access: {snapshot['access']}")
        print(f"Account status: {snapshot['account_status']}")
        print(f"Trading blocked: {snapshot['trading_blocked']}")
        print(f"Equity: ${snapshot['equity']:,.2f}")
        print(f"Cash: ${snapshot['cash']:,.2f}")
        print(f"Open positions: {len(snapshot['positions'])}")
        print(
            "Risk validation: "
            f"{'PASS' if snapshot['risk_passed'] else 'FAIL'}"
        )

        for error in snapshot["risk_errors"]:
            print(f"RISK ERROR: {error}")

        for warning in snapshot["risk_warnings"]:
            print(f"RISK WARNING: {warning}")

        for position in snapshot["positions"]:
            print(
                f"  {position['ticker']}: "
                f"${position['market_value']:,.2f}"
            )

        print("Execution enabled: False")
        print("Order submission: NOT USED")

        if not snapshot["risk_passed"]:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
