
import unittest

from trading_strategy import generate_signal


class TradingStrategyTests(unittest.TestCase):
    def setUp(self):
        self.bullish = {
            "close": 110,
            "EMA_20": 108,
            "EMA_50": 104,
            "RSI_14": 60,
            "MACD": 2.0,
            "MACD_Signal": 1.5,
            "ATR_14": 2.0,
        }

    def test_bullish_setup_returns_buy(self):
        self.assertEqual(generate_signal(self.bullish)["signal"], "BUY")

    def test_missing_data_returns_hold(self):
        result = generate_signal({"close": 100})
        self.assertEqual(result["signal"], "HOLD")
        self.assertTrue(result["risk_flags"])

    def test_high_volatility_returns_hold(self):
        data = {**self.bullish, "ATR_14": 8.0}
        self.assertEqual(generate_signal(data)["signal"], "HOLD")

    def test_conflicting_indicators_return_hold(self):
        data = {**self.bullish, "MACD": 1.0, "MACD_Signal": 2.0}
        self.assertEqual(generate_signal(data)["signal"], "HOLD")

    def test_bearish_setup_returns_sell(self):
        data = {
            "close": 90,
            "EMA_20": 95,
            "EMA_50": 100,
            "RSI_14": 40,
            "MACD": -2.0,
            "MACD_Signal": -1.0,
            "ATR_14": 2.0,
        }
        self.assertEqual(generate_signal(data)["signal"], "SELL")

    def test_nan_value_returns_hold(self):
        data = {**self.bullish, "RSI_14": float("nan")}
        result = generate_signal(data)
        self.assertEqual(result["signal"], "HOLD")
        self.assertTrue(result["risk_flags"])

    def test_zero_close_returns_hold(self):
        data = {**self.bullish, "close": 0}
        self.assertEqual(generate_signal(data)["signal"], "HOLD")

    def test_oversold_rsi_does_not_return_sell(self):
        data = {
            "close": 90,
            "EMA_20": 95,
            "EMA_50": 100,
            "RSI_14": 20,
            "MACD": -2.0,
            "MACD_Signal": -1.0,
            "ATR_14": 2.0,
        }
        self.assertEqual(generate_signal(data)["signal"], "HOLD")


if __name__ == "__main__":
    unittest.main(verbosity=2)
