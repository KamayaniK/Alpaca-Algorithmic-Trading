import unittest
from unittest.mock import patch

from run_all_36_strategies import analyze_payload


GOOD_INDICATORS = {
    "close": 200.0,
    "EMA_20": 195.0,
    "EMA_50": 190.0,
    "RSI_14": 58.0,
    "MACD": 2.0,
    "MACD_Signal": 1.0,
    "MACD_Histogram": 1.0,
    "ATR_14": 3.0,
    "RS_20D_vs_SPY": 0.03,
    "ADX_14": 30.0,
    "PLUS_DI_14": 25.0,
    "MINUS_DI_14": 15.0,
    "Volume_Ratio_5_20": 1.4,
    "Price_Change_1D": 0.02,
}


def news_result(status):
    return {
        "news_status": status,
        "news_check_passed": status == "CLEAR",
        "severe_negative_news": status == "SEVERE_NEGATIVE",
        "news_checked_at_utc": "2026-10-12T22:00:00+00:00",
        "news_articles_checked": 10,
        "news_matched_headlines": [],
        "news_reason": "Test fixture",
    }


class NewsGateTests(unittest.TestCase):
    @patch("news_screening.screen_news")
    def test_clear_news_allows_strategy_to_evaluate_buy(self, mock_news):
        mock_news.return_value = news_result("CLEAR")
        result = analyze_payload(
            "AAPL", {"latest_indicators": GOOD_INDICATORS}
        )
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["news_status"], "CLEAR")
        self.assertTrue(result["news_check_passed"])
        self.assertFalse(result["execution_enabled"])

    @patch("news_screening.screen_news")
    def test_severe_negative_news_blocks_buy(self, mock_news):
        mock_news.return_value = news_result("SEVERE_NEGATIVE")
        result = analyze_payload(
            "AAPL", {"latest_indicators": GOOD_INDICATORS}
        )
        self.assertNotEqual(result["signal"], "BUY")
        self.assertEqual(result["news_status"], "SEVERE_NEGATIVE")
        self.assertFalse(result["news_check_passed"])
        self.assertFalse(result["execution_enabled"])

    @patch("news_screening.screen_news")
    def test_unavailable_news_blocks_buy(self, mock_news):
        mock_news.return_value = news_result("UNAVAILABLE")
        result = analyze_payload(
            "AAPL", {"latest_indicators": GOOD_INDICATORS}
        )
        self.assertNotEqual(result["signal"], "BUY")
        self.assertEqual(result["news_status"], "UNAVAILABLE")
        self.assertFalse(result["news_check_passed"])
        self.assertFalse(result["execution_enabled"])

    @patch("news_screening.screen_news", side_effect=RuntimeError("test"))
    def test_news_exception_fails_closed(self, mock_news):
        result = analyze_payload(
            "AAPL", {"latest_indicators": GOOD_INDICATORS}
        )
        self.assertNotEqual(result["signal"], "BUY")
        self.assertEqual(result["news_status"], "UNAVAILABLE")
        self.assertFalse(result["execution_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
