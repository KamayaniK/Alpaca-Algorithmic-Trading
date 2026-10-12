import json
import unittest

from mcp_strategy_client import analyze_mcp_text


class MCPStrategyClientTests(unittest.TestCase):
    def test_valid_indicator_response_generates_buy(self):
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

        result = analyze_mcp_text(response)

        self.assertEqual(result["ticker"], "AMD")
        self.assertEqual(result["signal"], "BUY")

    def test_mcp_error_fails_safe_to_hold(self):
        response = json.dumps({
            "ticker": "AMD",
            "error": "Synthetic test error",
        })

        result = analyze_mcp_text(response)

        self.assertEqual(result["signal"], "HOLD")
        self.assertTrue(result["risk_flags"])

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(json.JSONDecodeError):
            analyze_mcp_text("not valid JSON")


if __name__ == "__main__":
    unittest.main(verbosity=2)
