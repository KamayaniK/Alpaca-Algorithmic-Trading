
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)

TICKERS = [
    "SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN",
    "JPM", "LLY", "META", "XOM", "PEP", "ABT",
]

BENCHMARK_FILE = ROOT / "SPY_daily_ohlcv.csv"
MIN_OBSERVATIONS = 60


def load_close(path):
    df = pd.read_csv(path)
    df.columns = [str(c).lower() for c in df.columns]

    required = {"timestamp", "close"}
    if not required.issubset(df.columns):
        raise ValueError(f"{path.name} must contain timestamp and close columns.")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    df = df.dropna(subset=["timestamp", "close"])
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp")

    return df.set_index("timestamp")["close"].rename(path.stem.split("_")[0])


benchmark = load_close(BENCHMARK_FILE)
benchmark_returns = benchmark.pct_change().rename("SPY")

results = []

for ticker in TICKERS:
    path = ROOT / f"{ticker}_daily_ohlcv_100.csv"

    if not path.exists():
        path = ROOT / f"{ticker}_daily_ohlcv.csv"

    if not path.exists():
        results.append({
            "ticker": ticker,
            "beta": None,
            "observations": 0,
            "status": "Missing stock CSV",
        })
        continue

    stock_close = load_close(path)
    stock_returns = stock_close.pct_change().rename(ticker)

    aligned = pd.concat(
        [stock_returns, benchmark_returns],
        axis=1,
        join="inner",
    ).dropna()

    if len(aligned) < MIN_OBSERVATIONS:
        results.append({
            "ticker": ticker,
            "beta": None,
            "observations": len(aligned),
            "status": f"Insufficient data: need at least {MIN_OBSERVATIONS}",
        })
        continue

    benchmark_variance = aligned["SPY"].var()
    if pd.isna(benchmark_variance) or benchmark_variance == 0:
        beta = None
        status = "Cannot calculate: benchmark variance is zero or invalid"
    else:
        beta = aligned[ticker].cov(aligned["SPY"]) / benchmark_variance
        status = "Calculated"

    results.append({
        "ticker": ticker,
        "beta": beta,
        "observations": len(aligned),
        "first_return_date": aligned.index.min().date().isoformat(),
        "last_return_date": aligned.index.max().date().isoformat(),
        "status": status,
    })

report = pd.DataFrame(results)
timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_UTC")

csv_path = REPORTS / f"mahi_beta_evidence_{timestamp}.csv"
md_path = REPORTS / f"mahi_beta_evidence_{timestamp}.md"

report.to_csv(csv_path, index=False)

with md_path.open("w", encoding="utf-8") as f:
    f.write("# Mahi's 12 Stocks — Beta Evidence\n\n")
    f.write(f"- Generated (UTC): {timestamp}\n")
    f.write("- Benchmark: SPY\n")
    f.write("- Method: covariance(stock daily returns, SPY daily returns) / variance(SPY daily returns)\n")
    f.write("- Minimum observations: 60 aligned daily returns\n")
    f.write("- Feed: Alpaca IEX; results depend on the available feed and period\n")
    f.write("- Interpretation: historical beta is an estimate, not a prediction or proof of future risk.\n\n")
    f.write(report.to_markdown(index=False))
    f.write("\n")

print("Beta calculation complete.")
print(report.to_string(index=False))
print("CSV report:", csv_path.relative_to(ROOT))
print("Markdown report:", md_path.relative_to(ROOT))
