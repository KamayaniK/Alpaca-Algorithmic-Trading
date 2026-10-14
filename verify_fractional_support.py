"""Read-only check of proposed assets using each member's paper credentials."""
import json
from pathlib import Path

from alpaca.trading.client import TradingClient
from team_accounts import load_account_config

PROPOSALS = {
    "Mahi": ["AMZN", "LLY", "META", "XOM"],
    "Ashima": ["CVX", "ISRG", "MSFT"],
    "Kamayani": ["AAPL", "ABBV", "PLTR", "UNH"],
}

def main():
    all_verified = True

    for member, tickers in PROPOSALS.items():
        print(f"\n{member}:")
        try:
            config = load_account_config(member)
            client = TradingClient(
                config.api_key,
                config.secret_key,
                paper=True,
            )
        except Exception as exc:
            all_verified = False
            print(f"  Account configuration unavailable: {type(exc).__name__}")
            continue

        for ticker in tickers:
            try:
                asset = client.get_asset(ticker)
                fractionable = getattr(asset, "fractionable", None)
                tradable = getattr(asset, "tradable", None)
                status = getattr(asset, "status", None)

                verified = (
                    fractionable is True
                    and tradable is True
                    and str(status).lower().endswith("active")
                )
                all_verified = all_verified and verified

                print(
                    f"  {ticker}: fractionable={fractionable}, "
                    f"tradable={tradable}, status={status}, "
                    f"verified={verified}"
                )
            except Exception as exc:
                all_verified = False
                print(f"  {ticker}: lookup failed ({type(exc).__name__})")

    print("\nFractional-share verification:", "PASS" if all_verified else "INCOMPLETE")
    print("Read-only asset lookups only. No orders submitted.")

if __name__ == "__main__":
    main()
