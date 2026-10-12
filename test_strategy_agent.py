
import unittest
from unittest.mock import patch

from strategy_agent import review_signal


class StrategyAgentTests(unittest.TestCase):
    def test_rejects_invalid_signal(self):
        with self.assertRaises(ValueError):
            review_signal({"signal": "MAYBE"})

    def test_rejects_non_dictionary(self):
        with self.assertRaises(TypeError):
            review_signal("BUY")

    def test_requires_model_key_before_calling_llm(self):
        signal = {
            "ticker": "AMD",
            "signal": "BUY",
            "reason": "Synthetic test signal",
            "risk_flags": [],
            "evidence": {"close": 110},
        }

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(EnvironmentError):
                review_signal(signal)


if __name__ == "__main__":
    unittest.main(verbosity=2)
