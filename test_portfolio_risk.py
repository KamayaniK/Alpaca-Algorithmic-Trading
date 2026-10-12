
import unittest

from portfolio_risk import (
    MAX_AI_HARDWARE_EXPOSURE,
    MAX_POSITION_VALUE,
    MAX_PLANNED_INVESTMENT,
    MAX_TECHNOLOGY_EXPOSURE,
    MIN_CASH_RESERVE,
    validate_portfolio,
    validate_signals,
)


class TestPortfolioRisk(unittest.TestCase):

    def test_empty_portfolio_passes(self):
        result = validate_portfolio({})
        self.assertTrue(result.passed)

    def test_position_over_13000_fails(self):
        result = validate_portfolio({"JPM": MAX_POSITION_VALUE + 1})
        self.assertFalse(result.passed)

    def test_investment_over_95000_fails(self):
        result = validate_portfolio({
            "JPM": 13_000,
            "LLY": 13_000,
            "GOOGL": 13_000,
            "AMZN": 13_000,
            "META": 13_000,
            "XOM": 13_000,
            "PEP": 13_000,
            "ABT": 5_001,
        })
        self.assertFalse(result.passed)

    def test_negative_position_fails(self):
        result = validate_portfolio({"JPM": -1_000})
        self.assertFalse(result.passed)
        self.assertTrue(any("short selling" in e.lower() for e in result.errors))

    def test_unknown_ticker_fails(self):
        result = validate_portfolio({"UNKNOWN": 1_000})
        self.assertFalse(result.passed)

    def test_technology_exposure_cap(self):
        result = validate_portfolio({
            "MSFT": 13_000,
            "AMD": 13_000,
            "GOOGL": 8_000,
        })
        self.assertFalse(result.passed)
        self.assertGreater(
            result.metrics["technology_exposure"],
            MAX_TECHNOLOGY_EXPOSURE,
        )

    def test_ai_hardware_exposure_cap(self):
        result = validate_portfolio({
            "AMD": 10_000,
            "SMCI": 10_000,
            "MU": 5_000,
        })
        self.assertFalse(result.passed)
        self.assertGreater(
            result.metrics["ai_hardware_exposure"],
            MAX_AI_HARDWARE_EXPOSURE,
        )

    def test_cash_reserve_is_reported(self):
        result = validate_portfolio({"JPM": 10_000})
        self.assertTrue(result.passed)
        self.assertEqual(
            result.metrics["cash_remaining"],
            90_000,
        )
        self.assertGreaterEqual(
            result.metrics["cash_remaining"],
            MIN_CASH_RESERVE,
        )

    def test_sell_signal_is_allowed_as_exit_only(self):
        result = validate_signals({"JPM": "SELL"})
        self.assertTrue(result.passed)

    def test_short_signal_is_rejected(self):
        result = validate_signals({"JPM": "SHORT"})
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
