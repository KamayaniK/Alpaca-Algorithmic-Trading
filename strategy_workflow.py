
"""Analysis-only trading workflow.

Fetches market indicators through MCP, generates deterministic signals,
and saves JSON and Markdown research reports. Does not place orders.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp_strategy_client import get_signal_from_mcp
from strategy_agent import review_signal


def create_research_report(signal_result: dict) -> dict:
    """Build a research report without calling an LLM or placing orders."""
    return {
        "ticker": signal_result.get("ticker", "UNKNOWN"),
        "signal": signal_result.get("signal", "HOLD"),
        "reason": signal_result.get("reason", "No reason supplied."),
        "risk_flags": signal_result.get("risk_flags", []),
        "evidence": signal_result.get("evidence", {}),
        "llm_review": None,
        "execution_enabled": False,
        "mode": "analysis_only",
    }


def _timestamp(now: Optional[datetime] = None) -> str:
    """Return a Windows-safe DDMMYYYY-HH-MM timestamp."""
    now = now or datetime.now()
    return now.strftime("%d%m%Y-%H-%M")


def save_report(report: dict, output_dir: str = "reports") -> Path:
    """Save the structured research report as JSON."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    ticker = str(report.get("ticker") or "UNKNOWN").upper()
    path = directory / f"{ticker}_research_report.json"

    path.write_text(
        json.dumps(report, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return path


def save_agent_markdown(
    agent_name: str,
    report: dict,
    output_dir: str = "model-run",
    now: Optional[datetime] = None,
) -> Path:
    """Save one agent's research output in a timestamped Markdown file."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    # Sanitize the name and avoid Windows-invalid filename characters.
    safe_name = "".join(
        character
        for character in agent_name
        if character.isalnum() or character in ("-", "_")
    )
    filename = f"{safe_name}{_timestamp(now)}.md"
    path = directory / filename

    evidence = report.get("evidence", {})
    risk_flags = report.get("risk_flags", [])

    lines = [
        f"# {agent_name} Research Output",
        "",
        f"- **Timestamp:** {(now or datetime.now()).isoformat(timespec='seconds')}",
        f"- **Ticker:** {report.get('ticker', 'UNKNOWN')}",
        f"- **Signal:** {report.get('signal', 'HOLD')}",
        f"- **Mode:** {report.get('mode', 'analysis_only')}",
        f"- **Execution enabled:** {report.get('execution_enabled', False)}",
        "",
        "## Reason",
        "",
        str(report.get("reason", "No reason supplied.")),
        "",
        "## Indicator Evidence",
        "",
    ]

    if evidence:
        for key, value in evidence.items():
            lines.append(f"- **{key}:** {value}")
    else:
        lines.append("No indicator evidence available.")

    lines.extend(["", "## Risk Flags", ""])

    if risk_flags:
        for flag in risk_flags:
            lines.append(f"- {flag}")
    else:
        lines.append("- No risk flags returned by the strategy.")

    lines.extend([
        "",
        "## Limitations",
        "",
        "- This is a research signal, not an order.",
        "- Paper trading results do not guarantee future performance.",
        "- No order was submitted by this workflow.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def run_workflow(
    ticker: str,
    *,
    include_llm_review: bool = False,
    output_dir: str = "reports",
    markdown_dir: str = "model-run",
) -> dict:
    """
    Run analysis through MCP and save research reports.

    LLM review is disabled by default. This workflow never submits orders.
    """
    ticker = ticker.strip().upper()
    if not ticker:
        raise ValueError("ticker must not be empty")

    # Fetch market data through MCP and generate the deterministic signal.
    signal_result = await get_signal_from_mcp(ticker)
    report = create_research_report(signal_result)

    # Save the deterministic strategy agent's Markdown output.
    markdown_paths = [
        str(save_agent_markdown(
            "strategyAgent",
            report,
            markdown_dir,
        ))
    ]

    # Optional LLM review: research only, no brokerage tools.
    if include_llm_review:
        review = review_signal(signal_result)
        report["llm_review"] = review

        review_report = {
            **report,
            "reason": review,
        }
        markdown_paths.append(
            str(save_agent_markdown(
                "llmReviewAgent",
                review_report,
                markdown_dir,
            ))
        )

    # Persist the final JSON report, including any optional review.
    json_path = save_report(report, output_dir)

    report["report_files"] = {
        "json": str(json_path),
        "markdown": markdown_paths,
    }

    return report


if __name__ == "__main__":
    result = asyncio.run(
        run_workflow(
            "AAPL",
            include_llm_review=False,
        )
    )

    print(json.dumps(result, indent=2, allow_nan=False))
