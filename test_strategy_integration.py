
import json
import unittest

from trading_strategy import generate_signal


def analyze_indicator_response(response_text: str) -> dict:
    """Convert an MCP-style indicator response into a research signal."""
    payload = json.loads(response_text)

    if payload.get("error"):
        return {
            "ticker": payload.get("ticker"),
            "signal": "HOLD",
            "reason": "Indicator tool returned an error.",
            "risk_flags": [str(payload["error"])],
            "evidence": {},
        }

    ticker = payload.get("ticker")
    indicators = payload.get("latest_indicators")

    if not ticker or not isinstance(indicators, dict):
        return {
            "ticker": ticker,
            "signal": "HOLD",
            "reason": "Indicator response has an unexpected format.",
            "risk_flags": ["Invalid MCP response"],
            "evidence": {},
        }

    result = generate_signal(indicators)
    return {"ticker": ticker, **result}


class StrategyIntegrationTests(unittest.TestCase):
    def test_mcp_style_response_generates_buy_signal(self):
        response = json.dumps({
            "ticker": "AMD",
            "latest_indicators": {
                "close": 110,
                "EMA_20": 108,
                "EMA_50": 104,
                "RSI_14": 60,
                "MACD": 2.0,
                "MACD_Signal": 1.5,
                "ATR_14": 2.0,
            },
        })

        result = analyze_indicator_response(response)

        self.assertEqual(result["ticker"], "AMD")
        self.assertEqual(result["signal"], "BUY")
        self.assertIn("reason", result)
        self.assertIn("evidence", result)

    def test_tool_error_fails_safe_to_hold(self):
        response = json.dumps({
            "ticker": "AMD",
            "error": "No local OHLCV data",
        })

        result = analyze_indicator_response(response)

        self.assertEqual(result["signal"], "HOLD")
        self.assertTrue(result["risk_flags"])

    def test_unexpected_response_fails_safe_to_hold(self):
        response = json.dumps({"ticker": "AMD"})

        result = analyze_indicator_response(response)

        self.assertEqual(result["signal"], "HOLD")
        self.assertTrue(result["risk_flags"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
