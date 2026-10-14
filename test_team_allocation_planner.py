from datetime import datetime, timezone

import json
import tempfile
import unittest
from pathlib import Path

from team_allocation_planner import build_member_proposal


class TeamAllocationPlannerTests(unittest.TestCase):
    def _write_report(self, folder, ticker, member, **overrides):
        report = {
            "ticker": ticker,
            "member": member,
            "signal": "BUY",
            "analysis_status": "OK",
            "execution_enabled": False,
            "news_status": "CLEAR",
            "news_check_passed": True,
            "risk_flags": [],
            "evidence": {"close": 100.0, "timestamp": datetime.now(timezone.utc).isoformat()},
        }
        report.update(overrides)
        (folder / f"{ticker}_research_report.json").write_text(
            json.dumps(report), encoding="utf-8"
        )

    def test_eligible_candidate_is_sized_and_execution_stays_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self._write_report(folder, "AMD", "Mahi")
            result = build_member_proposal("Mahi", folder)

        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["positions"][0]["proposed_dollars"], 13000.0)
        self.assertFalse(result["execution_enabled"])
        self.assertFalse(result["order_submission_used"])

    def test_unconfirmed_news_is_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self._write_report(
                folder, "AMD", "Mahi", news_check_passed=False
            )
            result = build_member_proposal("Mahi", folder)

        self.assertEqual(result["candidate_count"], 0)
        amd_exclusion = next(
            item for item in result["excluded"] if item["ticker"] == "AMD"
        )
        self.assertIn("News check not confirmed", amd_exclusion["reason"])

    def test_risk_flags_exclude_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self._write_report(
                folder, "AMD", "Mahi", risk_flags=["Manual review needed"]
            )
            result = build_member_proposal("Mahi", folder)

        self.assertEqual(result["candidate_count"], 0)

    def test_wrong_member_report_is_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            self._write_report(folder, "AMD", "Ashima")
            result = build_member_proposal("Mahi", folder)

        self.assertEqual(result["candidate_count"], 0)

    def test_unknown_member_is_rejected(self):
        with self.assertRaises(ValueError):
            build_member_proposal("Unknown", Path("."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
