
import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TICKERS = [
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
    "SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN",
    "GS", "ISRG", "CAT", "FCX", "PG", "CVX",
    "HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL",
    "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV"
]


async def call_and_print(session, name, arguments):
    result = await session.call_tool(name, arguments)

    if result.isError:
        raise RuntimeError(f"{name} returned an MCP error")

    text_items = [
        item.text for item in result.content
        if hasattr(item, "text")
    ]

    if not text_items:
        raise ValueError(f"{name} returned no text")

    payload = json.loads(text_items[0])

    if isinstance(payload, dict) and payload.get("error"):
        raise ValueError(str(payload["error"]))

    print(f"PASS {name}")
    print(json.dumps(payload, indent=2)[:1200])
    return payload


async def main():
    root = Path(__file__).resolve().parent
    server = StdioServerParameters(
        command="python",
        args=[str(root / "technical_indicators_mcp_server.py")],
        cwd=str(root),
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}

            required = {
                "get_account_summary",
                "get_stock_bars",
                "calculate_stock_indicators",
                "validate_local_stock_data",
            }

            print("MCP connection: PASS")
            print("Registered tools:", ", ".join(sorted(tool_names)))

            missing = required - tool_names
            if missing:
                raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")

            print("\n========== FOUR-TOOL TEST ==========")
            tests = [
                ("get_account_summary", {}),
                ("get_stock_bars", {"tickers": ["AMD"], "days": 5}),
                ("validate_local_stock_data", {"ticker": "AMD"}),
                ("calculate_stock_indicators", {"ticker": "AMD"}),
            ]

            tool_failures = []

            for name, arguments in tests:
                try:
                    await call_and_print(session, name, arguments)
                except Exception as error:
                    tool_failures.append((name, str(error)))
                    print(f"FAIL {name}: {error}")

            print("\n========== 36-STOCK INDICATOR TEST ==========")
            passed = []
            failed = []

            for ticker in TICKERS:
                try:
                    await call_and_print(
                        session,
                        "calculate_stock_indicators",
                        {"ticker": ticker},
                    )
                    passed.append(ticker)
                except Exception as error:
                    failed.append((ticker, str(error)))
                    print(f"FAIL {ticker}: {error}")

            print("\n========== FINAL SUMMARY ==========")
            print(f"Four-tool tests passed: {len(tests) - len(tool_failures)}/4")
            print(f"Four-tool tests failed: {len(tool_failures)}")
            print(f"36-stock indicator tests passed: {len(passed)}/36")
            print(f"36-stock indicator tests failed: {len(failed)}")

            if tool_failures:
                print("Tool failures:", tool_failures)
            if failed:
                print("Stock failures:", failed)


if __name__ == "__main__":
    asyncio.run(main())
