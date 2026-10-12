
import pandas as pd
from pathlib import Path

file_path = Path("AMD_daily_ohlcv.csv")

print("File exists:", file_path.exists())

df = pd.read_csv(file_path)

print("\nColumn names:")
print(df.columns.tolist())

print("\nFirst 3 rows:")
print(df.head(3).to_string(index=False))
