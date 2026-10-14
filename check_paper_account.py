"""Read-only Alpaca paper account check. Never submits orders."""

import os
from alpaca.trading.client import TradingClient


def main():
    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")

    if not key or not secret:
        raise SystemExit(
            "Missing ALPACA_API_KEY or ALPACA_SECRET_KEY environment variable."
        )

    client = TradingClient(key, secret, paper=True)
    account = client.get_account()
    positions = client.get_all_positions()

    print("Mode: PAPER / READ-ONLY")
    print("Account status:", account.status)
    print("Trading restricted:", account.trading_blocked)
    print("Equity: $", account.equity)
    print("Cash: $", account.cash)
    print("Open positions:", len(positions))
    print("Order submission: NOT USED")


if __name__ == "__main__":
    main()
