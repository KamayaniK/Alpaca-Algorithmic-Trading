"""Read-only verification of one configured Alpaca paper account."""
import argparse
import sys

from alpaca.trading.client import TradingClient
from team_accounts import load_account_config


def main():
    parser = argparse.ArgumentParser(
        description="Read-only Alpaca PAPER account check; never submits orders."
    )
    parser.add_argument(
        "member",
        choices=("Mahi", "Ashima", "Kamayani"),
        help="Which configured paper account to check",
    )
    args = parser.parse_args()

    try:
        config = load_account_config(args.member)
        client = TradingClient(
            api_key=config.api_key,
            secret_key=config.secret_key,
            paper=True,
        )
        account = client.get_account()
        positions = client.get_all_positions()

        print(f"Member: {config.member}")
        print("Mode: PAPER")
        print("Access: READ-ONLY")
        print(f"Account status: {account.status}")
        print(f"Trading blocked: {account.trading_blocked}")
        print(f"Equity: ${float(account.equity):,.2f}")
        print(f"Cash: ${float(account.cash):,.2f}")
        print(f"Open positions: {len(positions)}")
        print("Order submission: NOT USED")
        return 0
    except Exception as exc:
        # Avoid printing credential values or request headers.
        print(f"Account check failed ({type(exc).__name__}).")
        print("Check the selected member's paper credentials and connection.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
