from unittest import TestCase
from unittest.mock import patch

import run_all_36_strategies as runner


class RunnerRiskGateTests(TestCase):
    def test_invalid_signal_fails_safely(self):
        indicators = {
            "close": 100,
            "EMA_20": 99,
            "EMA_50": 98,
            "RSI_14": 55,
            "MACD": 1,
            "MACD_Signal": 0.5,
            "MACD_Histogram": 0.5,
            "ATR_14": 1,
            "RS_20D_vs_SPY": 1,
            "ADX_14": 25,
            "PLUS_DI_14": 30,
            "MINUS_DI_14": 10,
            "Volume_Ratio_5_20": 1.2,
            "Price_Change_1D": 1,
        }

        with patch.object(
            runner, "generate_signal",
            return_value={"signal": "SHORT", "reason": "test"}
        ), patch(
            "news_screening.screen_news",
            return_value={
                "news_status": "CLEAR",
                "news_check_passed": True,
                "severe_negative_news": False,
                "news_articles_checked": 1,
                "news_reason": "test",
            }
        ):
            result = runner.analyze_payload("AAPL", {
                "latest_indicators": indicators
            })

        self.assertEqual(result["signal"], "HOLD")
        self.assertEqual(result["analysis_status"], "ERROR")
        self.assertFalse(result["execution_enabled"])
        self.assertIn("Signal validation failed", result["reason"])

    def test_execution_remains_disabled_in_failure_result(self):
        result = runner.failure_result("AAPL", "test failure")
        self.assertEqual(result["signal"], "HOLD")
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(result["mode"], "analysis_only")


if __name__ == "__main__":
    import unittest
    unittest.main()
