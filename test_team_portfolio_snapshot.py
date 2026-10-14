import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from team_portfolio_snapshot import fetch_member_snapshot


def fake_account(equity="100000", cash="100000"):
    return SimpleNamespace(
        equity=equity,
        cash=cash,
        status="ACTIVE",
        trading_blocked=False,
    )


def fake_position(
    symbol="AMD",
    market_value="10000",
    qty="50",
    unrealized_pl="250",
):
    return SimpleNamespace(
        symbol=symbol,
        market_value=market_value,
        qty=qty,
        unrealized_pl=unrealized_pl,
    )


class TeamPortfolioSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.config = SimpleNamespace(
            member="Mahi",
            api_key="fake-paper-key",
            secret_key="fake-paper-secret",
            paper=True,
        )

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_empty_paper_account_snapshot_passes(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account()
        client.get_all_positions.return_value = []

        result = fetch_member_snapshot("Mahi")

        self.assertEqual(result["mode"], "PAPER")
        self.assertEqual(result["access"], "READ-ONLY")
        self.assertEqual(result["equity"], 100000.0)
        self.assertEqual(result["cash"], 100000.0)
        self.assertEqual(result["positions"], [])
        self.assertTrue(result["risk_passed"])
        self.assertFalse(result["execution_enabled"])
        self.assertFalse(result["order_submission_used"])
        client.get_account.assert_called_once_with()
        client.get_all_positions.assert_called_once_with()

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_valid_position_is_returned_and_validated(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="100000", cash="90000"
        )
        client.get_all_positions.return_value = [
            fake_position(market_value="10000")
        ]

        result = fetch_member_snapshot("Mahi")

        self.assertEqual(len(result["positions"]), 1)
        self.assertEqual(result["positions"][0]["ticker"], "AMD")
        self.assertEqual(result["positions"][0]["market_value"], 10000.0)
        self.assertTrue(result["risk_passed"])
        self.assertFalse(result["execution_enabled"])

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_wrong_member_ticker_fails_risk_validation(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="100000", cash="90000"
        )
        client.get_all_positions.return_value = [
            fake_position(symbol="SMCI", market_value="10000")
        ]

        result = fetch_member_snapshot("Mahi")

        self.assertFalse(result["risk_passed"])
        self.assertTrue(result["risk_errors"])
        self.assertFalse(result["execution_enabled"])

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_non_paper_configuration_is_rejected(
        self, mock_config, mock_client_class
    ):
        self.config.paper = False
        mock_config.return_value = self.config

        with self.assertRaises(RuntimeError):
            fetch_member_snapshot("Mahi")

        mock_client_class.assert_not_called()

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_account_api_error_propagates_without_orders(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.side_effect = RuntimeError("mock API failure")

        with self.assertRaisesRegex(RuntimeError, "mock API failure"):
            fetch_member_snapshot("Mahi")

        client.get_all_positions.assert_not_called()
        # The snapshot module must never submit, replace, or cancel orders.
        for method in (
            "submit_order",
            "replace_order_by_id",
            "cancel_order_by_id",
        ):
            self.assertFalse(
                getattr(client, method).called,
                f"Unexpected order method call: {method}",
            )

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_malformed_position_value_is_rejected(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="100000", cash="90000"
        )
        client.get_all_positions.return_value = [
            fake_position(market_value="not-a-number")
        ]

        with self.assertRaises(ValueError):
            fetch_member_snapshot("Mahi")

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_duplicate_positions_are_rejected(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="100000", cash="80000"
        )
        client.get_all_positions.return_value = [
            fake_position(symbol="AMD", market_value="10000"),
            fake_position(symbol=" amd ", market_value="10000"),
        ]

        with self.assertRaisesRegex(ValueError, "Duplicate position"):
            fetch_member_snapshot("Mahi")



    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_non_finite_account_equity_is_rejected(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="NaN", cash="100000"
        )
        client.get_all_positions.return_value = []

        with self.assertRaisesRegex(ValueError, "equity"):
            fetch_member_snapshot("Mahi")

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_negative_position_value_is_rejected(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="100000", cash="100000"
        )
        client.get_all_positions.return_value = [
            fake_position(market_value="-100")
        ]

        with self.assertRaisesRegex(ValueError, "market value"):
            fetch_member_snapshot("Mahi")

    @patch("team_portfolio_snapshot.TradingClient")
    @patch("team_portfolio_snapshot.load_account_config")
    def test_invalid_position_quantity_is_rejected(
        self, mock_config, mock_client_class
    ):
        mock_config.return_value = self.config
        client = mock_client_class.return_value
        client.get_account.return_value = fake_account(
            equity="100000", cash="90000"
        )
        client.get_all_positions.return_value = [
            fake_position(market_value="10000", qty="NaN")
        ]

        with self.assertRaisesRegex(ValueError, "quantity"):
            fetch_member_snapshot("Mahi")


if __name__ == "__main__":
    unittest.main(verbosity=2)
