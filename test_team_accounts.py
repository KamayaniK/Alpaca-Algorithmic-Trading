import unittest
from unittest.mock import patch

from team_accounts import load_account_config


class TestTeamAccounts(unittest.TestCase):
    def test_each_member_loads_separate_credentials(self):
        env = {
            "MAHI_ALPACA_API_KEY": "mahi-key",
            "MAHI_ALPACA_SECRET_KEY": "mahi-secret",
            "ASHIMA_ALPACA_API_KEY": "ashima-key",
            "ASHIMA_ALPACA_SECRET_KEY": "ashima-secret",
            "KAMAYANI_ALPACA_API_KEY": "kamayani-key",
            "KAMAYANI_ALPACA_SECRET_KEY": "kamayani-secret",
        }
        with patch.dict("os.environ", env, clear=True):
            configs = [
                load_account_config(name)
                for name in ("Mahi", "Ashima", "Kamayani")
            ]
        self.assertEqual(len({c.api_key for c in configs}), 3)
        self.assertTrue(all(c.paper for c in configs))

    def test_missing_credentials_fail_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "Missing paper credentials"):
                load_account_config("Mahi")

    def test_unknown_member_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown team member"):
            load_account_config("Unknown")

    def test_missing_secret_fails_closed(self):
        env = {"MAHI_ALPACA_API_KEY": "fake-key"}
        with patch.dict("os.environ", env, clear=True):
            with self.assertRaisesRegex(ValueError, "Missing paper credentials"):
                load_account_config("Mahi")


if __name__ == "__main__":
    unittest.main()
