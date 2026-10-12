
import requests
import time
from getpass import getpass

BASE_URL = "https://paper-api.alpaca.markets/v2/assets"
TICKERS = ["ISRG", "CAT", "FCX"]

api_key = getpass("Enter your PAPER API Key: ")
api_secret = getpass("Enter your PAPER Secret Key: ")

headers = {
    "APCA-API-KEY-ID": api_key,
    "APCA-API-SECRET-KEY": api_secret,
}

for ticker in TICKERS:
    for attempt in range(1, 4):
        try:
            response = requests.get(
                f"{BASE_URL}/{ticker}",
                headers=headers,
                timeout=45,
            )

            if response.status_code == 200:
                asset = response.json()
                status = asset.get("status")
                tradable = asset.get("tradable")
                print(
                    f"{ticker}: status={status}, "
                    f"tradable={tradable}"
                )
            else:
                print(
                    f"{ticker}: HTTP {response.status_code} - "
                    f"{response.text[:200]}"
                )
            break

        except requests.RequestException as error:
            print(
                f"{ticker}: attempt {attempt}/3 failed - "
                f"{type(error).__name__}"
            )
            if attempt < 3:
                time.sleep(3)
