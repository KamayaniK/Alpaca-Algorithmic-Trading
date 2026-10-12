
import requests
from alpaca_credentials import (
    ALPACA_API_KEY,
    ALPACA_SECRET_KEY,
    ALPACA_PAPER_BASE_URL,
)

BASE_URL = ALPACA_PAPER_BASE_URL.rstrip("/")

headers = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
}

try:
    response = requests.get(
        f"{BASE_URL}/v2/account",
        headers=headers,
        timeout=30,
    )

    print("HTTP Status:", response.status_code)

    if response.status_code == 200:
        account = response.json()
        print("Connection successful!")
        print("Account status:", account.get("status"))
        print("Trading blocked:", account.get("trading_blocked"))
        print("Paper account connection verified.")
    elif response.status_code in (401, 403):
        print("Authentication or permission failed.")
        print("Check that the credentials belong to your paper account.")
    else:
        print("Response:", response.text[:500])

except requests.RequestException as error:
    print("Connection error:", error)
