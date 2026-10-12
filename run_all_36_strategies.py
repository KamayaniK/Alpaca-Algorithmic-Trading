
"""Analysis-only batch strategy runner for the team's 36 stocks.

Fetches indicators in one MCP batch request, applies the existing
deterministic trading strategy, and saves team/member research reports.

This script does not submit orders.
"""

import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from trading_strategy import generate_signal


ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = ROOT / "technical_indicators_mcp_server.py"
REPORTS_DIR = ROOT / "reports" / "team_strategy_runs"

TEAM = {
    "Mahi": [
        "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
        "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    ],
    "Ashima": [
        "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
        "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    ],
    "Kamayani": [
        "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
        "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV",
    ],
}

ALL_TICKERS = [
    ticker
    for member_tickers in TEAM.values()
    for ticker in member_tickers
]


def validate_universe():
    """Catch duplicate or missing tickers before contacting MCP."""
    if len(ALL_TICKERS) != 36:
        raise ValueError(
            f"Expected 36 assigned tickers; found {len(ALL_TICKERS)}."
        )

    if len(set(ALL_TICKERS)) != len(ALL_TICKERS):
        raise ValueError("Duplicate ticker found in team allocations.")

    if not SERVER_SCRIPT.is_file():
        raise FileNotFoundError(
            f"MCP server not found: {SERVER_SCRIPT}"
        )


def failure_result(ticker, reason):
    """Return a clearly marked fail-safe research result."""
    return {
        "ticker": ticker,
        "member": member_for(ticker),
        "signal": "HOLD",
        "reason": reason,
        "risk_flags": ["Analysis failed; HOLD is not a trading instruction"],
        "evidence": {},
        "analysis_status": "ERROR",
        "execution_enabled": False,
        "mode": "analysis_only",
    }


def member_for(ticker):
    """Return the team member assigned to a ticker."""
    for member, tickers in TEAM.items():
        if ticker in tickers:
            return member
    return "Unassigned"


def analyze_payload(ticker, payload):
    """Apply indicators and a per-ticker news screen; never place orders."""
    if not isinstance(payload, dict):
        return failure_result(
            ticker, "MCP returned an unexpected result format."
        )

    if payload.get("error"):
        return failure_result(
            ticker, f"MCP indicator error: {payload['error']}"
        )

    indicators = payload.get("latest_indicators")
    if not isinstance(indicators, dict):
        return failure_result(
            ticker, "Response did not contain latest_indicators."
        )

    # Fail closed: news errors or inconclusive results block BUY signals.
    try:
        from news_screening import screen_news
        news = screen_news(ticker)
    except Exception as exc:
        news = {
            "news_status": "UNAVAILABLE",
            "news_check_passed": False,
            "severe_negative_news": False,
            "news_checked_at_utc": "",
            "news_articles_checked": 0,
            "news_matched_headlines": [],
            "news_reason": (
                f"News screening failed: {type(exc).__name__}: {exc}"
            ),
        }

    # Only an explicit CLEAR result permits the news gate to pass.
    news_passed = (
        news.get("news_status") == "CLEAR"
        and news.get("news_check_passed") is True
        and news.get("severe_negative_news") is False
    )
    indicators_for_strategy = dict(indicators)
    indicators_for_strategy["news_check_passed"] = news_passed
    indicators_for_strategy["severe_negative_news"] = (
        news.get("severe_negative_news") is True
    )

    try:
        signal = generate_signal(indicators_for_strategy)
    except Exception as exc:
        return failure_result(
            ticker, f"Strategy calculation failed: {exc}"
        )

    evidence = signal.get("evidence", {})
    if not isinstance(evidence, dict):
        evidence = {"original_evidence": evidence}
    else:
        evidence = dict(evidence)

    evidence["news_screening"] = news

    return {
        "ticker": ticker,
        "member": member_for(ticker),
        "signal": signal.get("signal", "HOLD"),
        "reason": signal.get("reason", "No reason supplied."),
        "risk_flags": signal.get("risk_flags", []),
        "evidence": evidence,
        "news_status": news.get("news_status", "UNAVAILABLE"),
        "news_check_passed": news_passed,
        "news_articles_checked": news.get("news_articles_checked", 0),
        "news_reason": news.get("news_reason", ""),
        "analysis_status": "OK",
        "execution_enabled": False,
        "mode": "analysis_only",
    }

async def fetch_batch_results():
    """Start one MCP server session and request all ticker indicators."""
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise RuntimeError(
            "Alpaca credentials are missing from the environment. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in PowerShell."
        )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(ROOT),
        env={
            **os.environ,
            "ALPACA_API_KEY": api_key,
            "ALPACA_SECRET_KEY": secret_key,
        },
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            available_tools = {
                tool.name for tool in tools_result.tools
            }

            tool_name = "calculate_multiple_stock_indicators"

            if tool_name not in available_tools:
                raise RuntimeError(
                    f"MCP server does not expose {tool_name}."
                )

            response = await session.call_tool(
                tool_name,
                {
                    "tickers": ALL_TICKERS,
                    "days": 150,
                },
            )

            if response.isError:
                raise RuntimeError(
                    "The batch MCP tool returned an error."
                )

            response_text = "\n".join(
                item.text
                for item in response.content
                if getattr(item, "type", None) == "text"
            )

            if not response_text:
                raise RuntimeError(
                    "The batch MCP tool returned no text response."
                )

            try:
                payload = json.loads(response_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Could not parse batch MCP JSON: {exc}"
                ) from exc

            if not isinstance(payload, dict):
                raise RuntimeError(
                    "Batch MCP response must be a JSON object."
                )

            if payload.get("error"):
                raise RuntimeError(str(payload["error"]))

            return payload


def save_json(path, data):
    """Write JSON without allowing NaN or infinity."""
    path.write_text(
        json.dumps(data, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def save_member_reports(results, run_dir):
    """Write separate CSV and Markdown reports for each member."""
    for member, tickers in TEAM.items():
        member_results = [
            result
            for result in results
            if result["ticker"] in tickers
        ]

        csv_path = run_dir / f"{member.lower()}_strategy_report.csv"
        md_path = run_dir / f"{member.lower()}_strategy_report.md"

        write_csv(csv_path, member_results)
        write_markdown(
            md_path,
            f"{member}'s 12-Stock Strategy Report",
            member_results,
        )


def write_csv(path, results):
    """Write strategy results and news screening details to CSV."""
    columns = [
        "ticker",
        "member",
        "signal",
        "reason",
        "risk_flags",
        "news_status",
        "news_check_passed",
        "news_articles_checked",
        "news_reason",
        "analysis_status",
        "execution_enabled",
        "mode",
        "evidence",
    ]

    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for result in results:
            row = dict(result)
            row["risk_flags"] = "; ".join(
                str(flag) for flag in result.get("risk_flags", [])
            )
            row["evidence"] = json.dumps(
                result.get("evidence", {}),
                allow_nan=False,
            )
            writer.writerow({
                column: row.get(column, "")
                for column in columns
            })


def write_markdown(path, title, results):
    """Write strategy summary including news screening status."""
    counts = {
        signal: sum(
            result.get("signal") == signal for result in results
        )
        for signal in ("BUY", "SELL", "HOLD")
    }

    news_counts = {
        status: sum(
            result.get("news_status", "UNAVAILABLE") == status
            for result in results
        )
        for status in ("CLEAR", "SEVERE_NEGATIVE", "UNAVAILABLE")
    }

    lines = [
        f"# {title}",
        "",
        f"- Generated (UTC): {datetime.now(timezone.utc).isoformat()}",
        "- Mode: analysis_only",
        "- Order execution: disabled",
        f"- Stocks analyzed: {len(results)}",
        f"- BUY signals: {counts['BUY']}",
        f"- SELL signals: {counts['SELL']}",
        f"- HOLD signals: {counts['HOLD']}",
        f"- Errors: {sum(r.get('analysis_status') == 'ERROR' for r in results)}",
        f"- News CLEAR: {news_counts['CLEAR']}",
        f"- News SEVERE_NEGATIVE: {news_counts['SEVERE_NEGATIVE']}",
        f"- News UNAVAILABLE: {news_counts['UNAVAILABLE']}",
        "",
        "| Ticker | Signal | Analysis status | News status | Articles checked | Reason |",
        "|---|---|---|---|---:|---|",
    ]

    for result in results:
        reason = str(result.get("reason", "")).replace("|", r"\|").replace("\n", " ")
        news_reason = str(result.get("news_reason", "")).replace("|", r"\|").replace("\n", " ")
        lines.append(
            f"| {result.get('ticker', '')} | "
            f"{result.get('signal', 'HOLD')} | "
            f"{result.get('analysis_status', 'ERROR')} | "
            f"{result.get('news_status', 'UNAVAILABLE')} | "
            f"{result.get('news_articles_checked', 0)} | "
            f"{reason} "
            f"{'? News: ' + news_reason if news_reason else ''} |"
        )

    lines.extend(["", "## Indicator and news evidence", ""])

    for result in results:
        lines.append(f"### {result.get('ticker', 'Unknown')}")
        lines.append("")
        lines.append(
            f"- Assigned member: {result.get('member', 'Unassigned')}"
        )
        lines.append(
            f"- Risk flags: {', '.join(result.get('risk_flags', [])) or 'None'}"
        )
        lines.append(
            f"- News status: {result.get('news_status', 'UNAVAILABLE')}"
        )
        lines.append(
            f"- News gate passed: {result.get('news_check_passed', False)}"
        )
        lines.append(
            f"- News articles checked: {result.get('news_articles_checked', 0)}"
        )
        if result.get("news_reason"):
            lines.append(f"- News screening reason: {result['news_reason']}")

        evidence = result.get("evidence", {})
        if evidence:
            for key, value in evidence.items():
                lines.append(f"- {key}: {value}")

        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")

async def main():
    validate_universe()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")
    run_dir = REPORTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running analysis-only batch for {len(ALL_TICKERS)} stocks.")
    print("Order execution is disabled.")
    print("Requesting indicators from MCP...")

    try:
        batch_payload = await fetch_batch_results()
    except Exception as exc:
        print(f"Batch request failed: {exc}")
        print(
            "No strategy results were generated. Check credentials, "
            "connectivity, and MCP server logs before retrying."
        )
        raise

    results = []

    for ticker in ALL_TICKERS:
        # The server returns a mapping keyed by ticker.
        ticker_payload = batch_payload.get(ticker)

        # Fail safely if the batch omitted a requested ticker.
        if ticker_payload is None:
            result = failure_result(
                ticker, "Ticker was missing from the batch response."
            )
        else:
            result = analyze_payload(ticker, ticker_payload)

        results.append(result)

        print(
            f"{ticker}: {result['signal']} "
            f"[{result['analysis_status']}] - {result['reason']}"
        )

        save_json(
            run_dir / f"{ticker}_research_report.json",
            result,
        )

    team_csv = run_dir / "team_36_stock_strategy_report.csv"
    team_md = run_dir / "team_36_stock_strategy_report.md"

    write_csv(team_csv, results)
    write_markdown(
        team_md,
        "Team 36-Stock Strategy Report",
        results,
    )
    save_member_reports(results, run_dir)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "analysis_only",
        "execution_enabled": False,
        "requested_tickers": len(ALL_TICKERS),
        "results": len(results),
        "analysis_successes": sum(
            r["analysis_status"] == "OK" for r in results
        ),
        "analysis_errors": sum(
            r["analysis_status"] == "ERROR" for r in results
        ),
        "signals": {
            signal: sum(r["signal"] == signal for r in results)
            for signal in ("BUY", "SELL", "HOLD")
        },
        "team_csv": str(team_csv),
        "team_markdown": str(team_md),
    }

    save_json(run_dir / "run_summary.json", summary)

    print("\n" + "=" * 50)
    print("TEAM STRATEGY RUN SUMMARY")
    print("=" * 50)
    print(f"Tickers: {summary['results']}")
    print(f"Analysis successes: {summary['analysis_successes']}")
    print(f"Analysis errors: {summary['analysis_errors']}")
    print(f"BUY: {summary['signals']['BUY']}")
    print(f"SELL: {summary['signals']['SELL']}")
    print(f"HOLD: {summary['signals']['HOLD']}")
    print(f"Reports folder: {run_dir}")
    print("Execution enabled: False")


if __name__ == "__main__":
    asyncio.run(main())
