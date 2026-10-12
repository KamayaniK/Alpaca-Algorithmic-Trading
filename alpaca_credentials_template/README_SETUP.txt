ALPACA CREDENTIALS SETUP

1. Put alpaca_credentials.py in the same folder as your other project scripts.
2. Open it and replace the two placeholder strings with your PAPER API key and
   PAPER secret key. Save the file.
3. In any Python script, import credentials like this:

   from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY

4. Keep alpaca_credentials.py private. Do not upload it to GitHub or share it.
5. Add the lines in .gitignore to your project's .gitignore file.
6. If a real key was already committed to GitHub, revoke/rotate it in Alpaca.

Example for historical market data:

   from alpaca_credentials import ALPACA_API_KEY, ALPACA_SECRET_KEY
   from alpaca.data.historical import StockHistoricalDataClient
   client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)

Use only PAPER credentials for this project. Never paste keys into ChatGPT.
