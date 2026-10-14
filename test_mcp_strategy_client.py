
import json
import unittest

from mcp_strategy_client import analyze_mcp_text


def bullish_indicators():
    return {
        "close": 110.0,
        "EMA_20": 108.0,
        "EMA_50": 104.0,
        "RSI_14": 60.0,
        "MACD": 2.0,
        "MACD_Signal": 1.5,
        "MACD_Histogram": 0.5,
        "ATR_14": 2.0,
        "RS_20D_vs_SPY": 0.05,
        "ADX_14": 30.0,
        "PLUS_DI_14": 35.0,
        "MINUS_DI_14": 15.0,
        "Volume_Ratio_5_20": 1.5,
        "Price_Change_1D": 0.02,
        "news_check_passed": True,
        "severe_negative_news": False,
    }


class MCPStrategyClientTests(unittest.TestCase):
    def test_valid_indicator_response_generates_buy(self):
        response = json.dumps({
            "ticker": "AMD",
            "latest_indicators": bullish_indicators(),
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

    def test_invalid_json_fails_safe_to_hold(self):
        result = analyze_mcp_text("not valid JSON")

        self.assertEqual(result["signal"], "HOLD")
        self.assertTrue(result["risk_flags"])
        self.assertEqual(result["reason"], "MCP response is not valid JSON.")


if __name__ == "__main__":
    unittest.main(verbosity=2)
