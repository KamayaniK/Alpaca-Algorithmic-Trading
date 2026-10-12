
import unittest

from trading_strategy import generate_signal


def make_indicators(
    close=110.0,
    ema20=108.0,
    ema50=104.0,
    rsi=60.0,
    histogram=0.5,
    relative_strength=0.05,
    adx=30.0,
    plus_di=35.0,
    minus_di=15.0,
    volume_ratio=1.5,
    price_change=0.02,
    atr=2.0,
):
    return {
        "close": close,
        "EMA_20": ema20,
        "EMA_50": ema50,
        "RSI_14": rsi,
        "MACD": histogram + 1.0,
        "MACD_Signal": 1.0,
        "MACD_Histogram": histogram,
        "ATR_14": atr,
        "RS_20D_vs_SPY": relative_strength,
        "ADX_14": adx,
        "PLUS_DI_14": plus_di,
        "MINUS_DI_14": minus_di,
        "Volume_Ratio_5_20": volume_ratio,
        "Price_Change_1D": price_change,
        "news_check_passed": True,
        "severe_negative_news": False,
    }


class TradingStrategyTests(unittest.TestCase):
    def setUp(self):
        self.bullish = make_indicators()

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
        data = {
            **self.bullish,
            "MACD_Histogram": -0.5,
            "MACD": 0.5,
            "MACD_Signal": 1.0,
            "RS_20D_vs_SPY": -0.05,
            "PLUS_DI_14": 15.0,
            "MINUS_DI_14": 35.0,
            "Price_Change_1D": -0.02,
        }
        self.assertEqual(generate_signal(data)["signal"], "HOLD")

    def test_bearish_setup_returns_sell(self):
        data = make_indicators(
            close=90.0,
            ema20=95.0,
            ema50=100.0,
            rsi=40.0,
            histogram=-0.5,
            relative_strength=-0.05,
            adx=30.0,
            plus_di=15.0,
            minus_di=35.0,
            volume_ratio=1.5,
            price_change=-0.02,
        )
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
        data = make_indicators(
            rsi=20.0,
            histogram=0.0,
            relative_strength=0.0,
            adx=20.0,
            plus_di=20.0,
            minus_di=20.0,
            volume_ratio=1.0,
            price_change=0.0,
        )
        self.assertEqual(generate_signal(data)["signal"], "HOLD")


if __name__ == "__main__":
    unittest.main(verbosity=2)
