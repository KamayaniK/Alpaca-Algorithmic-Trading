
import requests
from getpass import getpass

BASE_URL = "https://paper-api.alpaca.markets/v2/assets"

api_key = getpass("Enter your PAPER API Key: ")
api_secret = getpass("Enter your PAPER Secret Key: ")

headers = {
    "APCA-API-KEY-ID": api_key,
    "APCA-API-SECRET-KEY": api_secret,
}

ticker = "AAPL"

response = requests.get(
    f"{BASE_URL}/{ticker}",
    headers=headers,
    timeout=20,
)

print("HTTP Status:", response.status_code)

if response.status_code == 200:
    asset = response.json()
    print("Ticker:", asset.get("symbol"))
    print("Company:", asset.get("name"))
    print("Status:", asset.get("status"))
    print("Tradable:", asset.get("tradable"))
else:
    print("Error response:", response.text[:500])
