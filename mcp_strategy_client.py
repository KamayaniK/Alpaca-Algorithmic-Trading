"""MCP-to-strategy integration helpers.

Importing this module does not launch the MCP server or require API keys.
"""

import os
import json
import sys
from pathlib import Path

from test_strategy_integration import analyze_indicator_response


PROJECT_ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = PROJECT_ROOT / "technical_indicators_mcp_server.py"


def analyze_mcp_text(response_text: str) -> dict:
    """Convert a JSON response from the MCP indicator tool into a signal."""
    return analyze_indicator_response(response_text)


async def get_signal_from_mcp(ticker: str) -> dict:
    """Launch the MCP server, request indicators, and generate a signal."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    ticker = ticker.strip().upper()

    if not ticker:
        raise ValueError("ticker must not be empty")

    if not SERVER_SCRIPT.is_file():
        raise FileNotFoundError(f"MCP server not found: {SERVER_SCRIPT}")

    # Read credentials from environment variables.
    # Never hardcode API keys or secret keys in this file.
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        raise RuntimeError(
            "Alpaca credentials are missing. Set ALPACA_API_KEY and "
            "ALPACA_SECRET_KEY in your environment before running."
        )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        env={
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
                raise RuntimeError(
                    "MCP server does not expose calculate_stock_indicators"
                )

            result = await session.call_tool(
                "calculate_stock_indicators",
                {"ticker": ticker},
            )

            if result.isError:
                return {
                    "ticker": ticker,
                    "signal": "HOLD",
                    "reason": "MCP indicator tool returned an error.",
                    "risk_flags": ["MCP tool error"],
                    "evidence": {},
                }

            response_text = "\n".join(
                item.text
                for item in result.content
                if getattr(item, "type", None) == "text"
            )

            if not response_text:
                return {
                    "ticker": ticker,
                    "signal": "HOLD",
                    "reason": "MCP tool returned no text response.",
                    "risk_flags": ["Empty MCP response"],
                    "evidence": {},
                }

            try:
                output = analyze_mcp_text(response_text)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                return {
                    "ticker": ticker,
                    "signal": "HOLD",
                    "reason": "Could not parse MCP indicator response.",
                    "risk_flags": [str(exc)],
                    "evidence": {},
                }

            output.setdefault("ticker", ticker)
            return output