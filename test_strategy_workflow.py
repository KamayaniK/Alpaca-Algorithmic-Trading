import json
import tempfile
import unittest

from strategy_workflow import create_research_report, save_report


class StrategyWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.signal = {
            "ticker": "AMD",
            "signal": "BUY",
            "reason": "Synthetic test signal",
            "risk_flags": [],
            "evidence": {"close": 110.0},
        }

    def test_report_preserves_signal_and_disables_execution(self):
        report = create_research_report(self.signal)

        self.assertEqual(report["ticker"], "AMD")
        self.assertEqual(report["signal"], "BUY")
        self.assertFalse(report["execution_enabled"])
        self.assertIsNone(report["llm_review"])

    def test_report_handles_missing_optional_fields(self):
        report = create_research_report({"signal": "HOLD"})

        self.assertEqual(report["signal"], "HOLD")
        self.assertEqual(report["risk_flags"], [])
        self.assertEqual(report["evidence"], {})

    def test_report_saves_as_valid_json(self):
        report = create_research_report(self.signal)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = save_report(report, temp_dir)

            self.assertTrue(path.is_file())
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["ticker"], "AMD")
            self.assertEqual(saved["signal"], "BUY")
            self.assertFalse(saved["execution_enabled"])
            self.assertIsNone(saved["llm_review"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
