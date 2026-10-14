import unittest

from team_portfolio_risk import validate_member_portfolio


class TeamPortfolioRiskTests(unittest.TestCase):
    def test_empty_portfolio_passes_for_each_member(self):
        for member in ("Mahi", "Ashima", "Kamayani"):
            with self.subTest(member=member):
                result = validate_member_portfolio(
                    member, {}, account_equity=100000, account_cash=100000
                )
                self.assertTrue(result.passed, result.errors)

    def test_wrong_member_ticker_is_rejected(self):
        result = validate_member_portfolio(
            "Mahi", {"SMCI": 1000}, account_equity=100000, account_cash=99000
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("not assigned" in e for e in result.errors))

    def test_position_cap_is_enforced(self):
        result = validate_member_portfolio(
            "Mahi", {"AMD": 14000}, account_equity=100000, account_cash=86000
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("position cap" in e for e in result.errors))

    def test_cash_snapshot_mismatch_is_rejected(self):
        result = validate_member_portfolio(
            "Mahi", {"AMD": 1000}, account_equity=100000, account_cash=100000
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("does not reconcile" in e for e in result.errors))

    def test_unknown_member_is_rejected(self):
        result = validate_member_portfolio(
            "Unknown", {}, account_equity=100000, account_cash=100000
        )
        self.assertFalse(result.passed)

    def test_negative_account_cash_is_rejected(self):
        result = validate_member_portfolio(
            "Mahi", {}, account_equity=100000, account_cash=-1
        )
        self.assertFalse(result.passed)

    def test_technology_exposure_cap_is_enforced(self):
        positions = {
            "GOOGL": 12000,
            "AMZN": 12000,
            "META": 12000,
        }
        result = validate_member_portfolio(
            "Mahi",
            positions,
            account_equity=100000,
            account_cash=64000,
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("technology exposure" in e.lower() for e in result.errors),
            result.errors,
        )

    def test_ai_hardware_exposure_cap_is_enforced(self):
        positions = {"SNDK": 12000, "AMD": 12000}
        result = validate_member_portfolio(
            "Mahi",
            positions,
            account_equity=100000,
            account_cash=76000,
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("ai-hardware exposure" in e.lower() for e in result.errors),
            result.errors,
        )

    def test_investment_budget_is_enforced(self):
        # Eight positions of $12,000 each exceed the $95,000 budget.
        # The $4,000 cash balance also breaches the minimum reserve.
        positions = {
            "SNDK": 12000,
            "AMD": 12000,
            "APP": 12000,
            "MRNA": 12000,
            "JPM": 12000,
            "LLY": 12000,
            "XOM": 12000,
            "PEP": 12000,
        }
        result = validate_member_portfolio(
            "Mahi",
            positions,
            account_equity=100000,
            account_cash=4000,
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any(
                "investment" in e.lower() or "cash" in e.lower()
                for e in result.errors
            ),
            result.errors,
        )

    def test_non_finite_position_value_is_rejected(self):
        result = validate_member_portfolio(
            "Mahi",
            {"AMD": float("nan")},
            account_equity=100000,
            account_cash=100000,
        )
        self.assertFalse(result.passed)
        self.assertTrue(result.errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
