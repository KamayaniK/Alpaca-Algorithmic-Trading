"""Equal-dollar allocation proposals. Analysis only; never submits orders."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from portfolio_risk import (
    MAX_PLANNED_INVESTMENT,
    MAX_POSITION_VALUE,
    MIN_CASH_RESERVE,
    validate_portfolio,
)
from team_portfolio_risk import TEAM_TICKERS

ROOT = Path(__file__).resolve().parent
DEFAULT_REPORT_DIR = ROOT / "reports" / "team_strategy_runs" / "20261014_145900_UTC"
OUTPUT_DIR = ROOT / "reports" / "allocation_proposals"

# Conservative calendar-day limit. Missing or invalid timestamps fail closed.
MAX_BAR_AGE_DAYS = 5


def _validate_bar_timestamp(value: Any) -> tuple[bool, str]:
    """Require a valid, timezone-aware, recent market-bar timestamp."""
    if not isinstance(value, str) or not value.strip():
        return False, "Bar timestamp is missing."

    try:
        timestamp = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )
    except (ValueError, OverflowError):
        return False, "Bar timestamp is malformed."

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        return False, "Bar timestamp must include a timezone."

    timestamp = timestamp.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)

    if timestamp > now:
        return False, "Bar timestamp is in the future."

    if (now - timestamp).total_seconds() > MAX_BAR_AGE_DAYS * 86400:
        return False, "Bar timestamp is stale."

    return True, "Timestamp valid."


def _eligible_report(
    path: Path, member: str
) -> tuple[dict[str, Any] | None, str]:
    """Return a BUY candidate only if identity, evidence, news, and risk checks pass."""
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Report unreadable: {exc}"

    if not isinstance(report, dict):
        return None, "Report must contain a JSON object."

    ticker = report.get("ticker")
    if (
        not isinstance(ticker, str)
        or ticker.strip().upper() not in TEAM_TICKERS[member]
    ):
        return None, "Ticker missing or not assigned to this member."

    ticker = ticker.strip().upper()

    if report.get("member") != member:
        return None, "Report member does not match requested member."

    if report.get("execution_enabled") is not False:
        return None, "Report is not explicitly marked execution-disabled."

    if report.get("analysis_status") != "OK":
        return None, "Analysis status is not OK."

    if str(report.get("signal", "")).upper() != "BUY":
        return None, "Signal is not BUY."

    if report.get("news_check_passed") is not True:
        return None, "News check not confirmed."

    flags = report.get("risk_flags", [])
    if not isinstance(flags, list) or flags:
        return None, "Risk flags exist or are malformed; manual review required."

    evidence = report.get("evidence")
    if not isinstance(evidence, dict):
        return None, "Evidence is missing."

    timestamp_ok, timestamp_reason = _validate_bar_timestamp(
        evidence.get("timestamp")
    )
    if not timestamp_ok:
        return None, timestamp_reason

    close = evidence.get("close")
    if (
        not isinstance(close, (int, float))
        or isinstance(close, bool)
        or not math.isfinite(close)
        or close <= 0
    ):
        return None, "Valid positive close price is unavailable."

    return {
        "ticker": ticker,
        "close": float(close),
        "timestamp": evidence["timestamp"],
        "news_status": report.get("news_status", "UNAVAILABLE"),
    }, "Eligible"


def build_member_proposal(
    member: str,
    report_dir: Path = DEFAULT_REPORT_DIR,
) -> dict[str, Any]:
    """Build an analysis-only proposal; does not access Alpaca or submit orders."""
    if member not in TEAM_TICKERS:
        raise ValueError(f"Unknown team member: {member!r}")

    candidates: list[dict[str, Any]] = []
    exclusions: list[dict[str, str]] = []

    for ticker in sorted(TEAM_TICKERS[member]):
        path = report_dir / f"{ticker}_research_report.json"
        if not path.is_file():
            exclusions.append({
                "ticker": ticker,
                "reason": "Research report missing.",
            })
            continue

        candidate, reason = _eligible_report(path, member)
        if candidate is None:
            exclusions.append({"ticker": ticker, "reason": reason})
        else:
            candidates.append(candidate)

    # Equal-dollar sizing, capped per position and across the planned budget.
    per_position = (
        min(MAX_POSITION_VALUE, MAX_PLANNED_INVESTMENT / len(candidates))
        if candidates
        else 0.0
    )
    positions = {
        item["ticker"]: round(per_position, 2)
        for item in candidates
    }
    risk = validate_portfolio(positions)

    proposal_positions = []
    for item in candidates:
        dollars = positions[item["ticker"]]
        proposal_positions.append({
            "ticker": item["ticker"],
            "reference_close": item["close"],
            "reference_bar_timestamp": item["timestamp"],
            "proposed_dollars": dollars,
            "estimated_shares": round(dollars / item["close"], 6),
            "fractional_shares_assumed": None,
            "fractional_share_support": "NOT_VERIFIED",
        })

    return {
        "member": member,
        "mode": "analysis_only",
        "execution_enabled": False,
        "order_submission_used": False,
        "candidate_count": len(candidates),
        "positions": proposal_positions,
        "excluded": exclusions,
        "risk_validation": risk.to_dict(),
        "cash_reserve_minimum": MIN_CASH_RESERVE,
        "note": (
            "Research proposal only. Each reference bar timestamp is checked "
            "against a conservative calendar-day limit. This is not a guarantee "
            "of a current executable price. Fractional-share support has not "
            "been verified. Quantities are estimates only. No orders submitted."
        ),
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_passed = True

    for member in ("Mahi", "Ashima", "Kamayani"):
        proposal = build_member_proposal(member)
        out_path = OUTPUT_DIR / f"{member.lower()}_allocation_proposal.json"
        out_path.write_text(
            json.dumps(proposal, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )

        risk = proposal["risk_validation"]
        all_passed = all_passed and risk["passed"]

        print(
            f"{member}: candidates={proposal['candidate_count']}, "
            f"positions={len(proposal['positions'])}, "
            f"risk_passed={risk['passed']}, "
            f"execution_enabled={proposal['execution_enabled']}"
        )

        for error in risk["errors"]:
            print(f"  RISK ERROR: {error}")
        for item in proposal["excluded"]:
            print(f"  EXCLUDED {item['ticker']}: {item['reason']}")
        print(f"  Report: {out_path}")

    print("Analysis only. Order execution disabled; no orders submitted.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
