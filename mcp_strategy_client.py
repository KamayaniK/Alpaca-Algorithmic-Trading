
"""MCP-to-strategy integration helpers.

This module generates research signals only and never submits orders.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

from strategy_response_parser import analyze_indicator_response


PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = PROJECT_ROOT / "technical_indicators_mcp_server.py"


def _hold(
    ticker: str,
    reason: str,
    risk_flags: list[str] | None = None,
) -> dict[str, Any]:
    """Return a fail-safe HOLD response."""
    return {
        "ticker": ticker,
        "signal": "HOLD",
        "reason": reason,
        "risk_flags": risk_flags or [],
        "evidence": {},
    }


def analyze_mcp_text(response_text: str) -> dict[str, Any]:
    """Parse MCP response text into a research signal."""
    try:
        result = analyze_indicator_response(response_text)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return _hold(
            "",
            "Could not parse MCP indicator response.",
            [str(exc)],
        )

    if not isinstance(result, dict):
        return _hold(
            "",
            "MCP parser returned an invalid result.",
            ["Invalid parser result"],
        )

    if result.get("signal") not in {"BUY", "SELL", "HOLD"}:
        return _hold(
            str(result.get("ticker", "")),
            "MCP parser returned an invalid signal.",
            ["Invalid signal"],
        )

    return result


async def get_signal_from_mcp(ticker: str) -> dict[str, Any]:
    """Request indicator data from MCP and return a research signal."""
    ticker = ticker.strip().upper() if isinstance(ticker, str) else ""

    if not ticker:
        raise ValueError("ticker must not be empty")

    if not SERVER_SCRIPT.is_file():
        return _hold(
            ticker,
            f"MCP server not found: {SERVER_SCRIPT}",
            ["MCP server missing"],
        )

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        return _hold(
            ticker,
            "Alpaca credentials are missing from environment variables.",
            ["Missing Alpaca credentials"],
        )

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=sys.executable,
            args=[str(SERVER_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env={
                **os.environ,
                "ALPACA_API_KEY": api_key,
                "ALPACA_SECRET_KEY": secret_key,
            },
        )

        async with stdio_client(server_params) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                tools_result = await session.list_tools()
                available_tools = {
                    tool.name for tool in tools_result.tools
                }

                if "calculate_stock_indicators" not in available_tools:
                    return _hold(
                        ticker,
                        "Required MCP indicator tool is unavailable.",
                        ["MCP tool unavailable"],
                    )

                result = await session.call_tool(
                    "calculate_stock_indicators",
                    {"ticker": ticker},
                )

                if result.isError:
                    return _hold(
                        ticker,
                        "MCP indicator tool returned an error.",
                        ["MCP tool error"],
                    )

                response_text = "\n".join(
                    item.text
                    for item in result.content
                    if getattr(item, "type", None) == "text"
                    and isinstance(getattr(item, "text", None), str)
                )

                if not response_text.strip():
                    return _hold(
                        ticker,
                        "MCP tool returned no text response.",
                        ["Empty MCP response"],
                    )

                output = analyze_mcp_text(response_text)
                output.setdefault("ticker", ticker)
                return output

    except Exception as exc:
        return _hold(
            ticker,
            "MCP request failed; no trade signal was authorized.",
            [f"{type(exc).__name__}: {exc}"],
        )


if __name__ == "__main__":
    print(
        "MCP strategy client loaded. "
        "Import this module or call get_signal_from_mcp() from your workflow."
    )
