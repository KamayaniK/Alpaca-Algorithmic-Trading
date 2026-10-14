"""Research-only historical backtest for Alpaca Algorithmic Trading.

Uses the project's real indicators.calculate_indicators and trading_strategy.generate_signal.
Signals are formed at the close and acted on at the next session's open.
Historical news decisions are unavailable: news_check_passed=True is used only to
measure technical-signal performance. Results are NOT a full-strategy validation.
No broker/network imports and no order execution.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from indicators.technical_indicators import calculate_indicators
from trading_strategy import generate_signal

EXECUTION_ENABLED = False
INITIAL_EQUITY = 100_000.0
MAX_PLANNED_INVESTMENT = 95_000.0
CASH_RESERVE = 5_000.0
MAX_POSITION_VALUE = 13_000.0
# Illustrative cost per side: 10 bps (0.10%). Change only with a justified estimate.
COST_BPS_PER_SIDE = 10.0
MAX_ATR_PCT = 5.0

MEMBERS = {
    "Mahi": ["SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN", "JPM", "LLY", "META", "XOM", "PEP", "ABT"],
    "Ashima": ["SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN", "GS", "ISRG", "CAT", "FCX", "PG", "CVX"],
    "Kamayani": ["HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL", "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV"],
}
ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "reports" / "backtest_20261014"


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return float((equity / equity.cummax() - 1.0).min())


def load_frame(ticker: str) -> pd.DataFrame:
    path = ROOT / f"{ticker}_daily_ohlcv_100.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing historical file: {path.name}")
    df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    df = df.sort_values("timestamp").drop_duplicates("timestamp", keep="last").reset_index(drop=True)
    return df


def run_ticker(ticker: str, spy: pd.DataFrame) -> tuple[dict, list[dict]]:
    bars = load_frame(ticker)
    # Indicators are calculated using only current and prior bars.
    ind = calculate_indicators(bars, spy_df=spy)
    if "timestamp" not in ind:
        raise ValueError(f"{ticker}: indicator output has no timestamp")
    ind["timestamp"] = pd.to_datetime(ind["timestamp"], utc=True, errors="coerce")
    ind["signal"] = "HOLD"
    for i, row in ind.iterrows():
        # Skip warm-up rows; generate_signal safely returns HOLD for invalid rows.
        values = row.to_dict()
        values["MACD_Histogram_Previous"] = (
            ind.iloc[i - 1].get("MACD_Histogram") if i > 0 else None
        )
        # Historical news status is unknown. True here is an explicit technical-only
        # proxy so we can test the indicator rules; it is not historical news evidence.
        values["news_check_passed"] = True
        values["severe_negative_news"] = False
        result = generate_signal(values, max_atr_pct=MAX_ATR_PCT)
        ind.at[i, "signal"] = result.get("signal", "HOLD")

    # Single-stock long-only simulation. Signal at close t executes at open t+1.
    # Entry is capped at $13k; no short selling. Cash is not levered.
    cash = INITIAL_EQUITY
    shares = 0.0
    entry_cost = 0.0
    trades: list[dict] = []
    daily = []
    cost_rate = COST_BPS_PER_SIDE / 10_000.0

    for i, row in ind.iterrows():
        # Process yesterday's close signal at today's open.
        if i > 0:
            prior_signal = ind.iloc[i - 1]["signal"]
            open_px = float(row["open"])
            if prior_signal == "BUY" and shares == 0 and cash > CASH_RESERVE:
                spend = min(MAX_POSITION_VALUE, MAX_PLANNED_INVESTMENT, cash - CASH_RESERVE)
                if spend > 0 and open_px > 0:
                    gross = spend
                    fee = gross * cost_rate
                    shares = (gross - fee) / open_px
                    cash -= gross
                    entry_cost = fee
                    trades.append({
                        "ticker": ticker, "entry_timestamp": str(row["timestamp"]),
                        "entry_price": open_px, "shares": shares, "entry_cost": fee,
                        "exit_timestamp": None, "exit_price": None, "exit_cost": None,
                        "gross_pnl": None, "net_pnl": None,
                    })
            elif prior_signal == "SELL" and shares > 0:
                gross = shares * open_px
                fee = gross * cost_rate
                cash += gross - fee
                trade = trades[-1]
                trade["exit_timestamp"] = str(row["timestamp"])
                trade["exit_price"] = open_px
                trade["exit_cost"] = fee
                trade["gross_pnl"] = (open_px - trade["entry_price"]) * shares
                trade["net_pnl"] = trade["gross_pnl"] - trade["entry_cost"] - fee
                shares = 0.0
                entry_cost = 0.0

        close_px = float(row["close"])
        equity = cash + shares * close_px
        daily.append({
            "timestamp": row["timestamp"], "ticker": ticker,
            "equity": equity, "cash": cash, "shares": shares,
            "close": close_px, "signal_at_close": row["signal"],
        })

    # Liquidate remaining position at final close for a comparable realized result.
    if shares > 0 and len(ind):
        last = ind.iloc[-1]
        px = float(last["close"])
        gross = shares * px
        fee = gross * cost_rate
        cash += gross - fee
        trade = trades[-1]
        trade["exit_timestamp"] = str(last["timestamp"]) + " (final-close liquidation)"
        trade["exit_price"] = px
        trade["exit_cost"] = fee
        trade["gross_pnl"] = (px - trade["entry_price"]) * shares
        trade["net_pnl"] = trade["gross_pnl"] - trade["entry_cost"] - fee
        shares = 0.0
        if daily:
            daily[-1]["equity"] = cash

    daily_df = pd.DataFrame(daily)
    closed = [t for t in trades if t["exit_price"] is not None]
    final_equity = float(daily_df["equity"].iloc[-1]) if not daily_df.empty else INITIAL_EQUITY
    result = {
        "ticker": ticker,
        "rows": int(len(ind)),
        "start": str(ind["timestamp"].min()) if len(ind) else None,
        "end": str(ind["timestamp"].max()) if len(ind) else None,
        "initial_equity": INITIAL_EQUITY,
        "final_equity": final_equity,
        "return_pct": (final_equity / INITIAL_EQUITY - 1) * 100,
        "max_drawdown_pct": max_drawdown(daily_df["equity"]) * 100 if len(daily_df) else 0,
        "closed_trades": len(closed),
        "wins": sum((t["net_pnl"] or 0) > 0 for t in closed),
        "win_rate_pct": (100 * sum((t["net_pnl"] or 0) > 0 for t in closed) / len(closed)) if closed else None,
        "estimated_costs": sum((t.get("entry_cost") or 0) + (t.get("exit_cost") or 0) for t in closed),
        "cost_bps_per_side": COST_BPS_PER_SIDE,
    }
    for trade in trades:
        trade["member"] = next((m for m, tickers in MEMBERS.items() if ticker in tickers), "Unknown")
    return result, trades


def main() -> None:
    if EXECUTION_ENABLED:
        raise RuntimeError("Safety stop: this script must remain research-only.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    spy = load_frame("SPY")
    summaries = []
    all_trades = []
    failures = []
    for member, tickers in MEMBERS.items():
        for ticker in tickers:
            try:
                summary, trades = run_ticker(ticker, spy)
                summary["member"] = member
                summaries.append(summary)
                all_trades.extend(trades)
                print(f"{member:9} {ticker:5} return={summary['return_pct']:8.2f}% "
                      f"maxDD={summary['max_drawdown_pct']:7.2f}% trades={summary['closed_trades']}")
            except Exception as exc:
                failures.append({"ticker": ticker, "member": member, "error": str(exc)})
                print(f"ERROR {member} {ticker}: {exc}")

    # Benchmark: equal-weight basket of the same 36 stocks, buy-and-hold close returns.
    benchmark_rows = []
    for ticker in [t for ts in MEMBERS.values() for t in ts]:
        try:
            df = load_frame(ticker)
            joined = df[["timestamp", "close"]].merge(
                spy[["timestamp", "close"]], on="timestamp", how="inner", suffixes=("_stock", "_spy")
            )
            if len(joined) >= 2:
                benchmark_rows.append({
                    "ticker": ticker,
                    "stock_buy_hold_return_pct": (joined.close_stock.iloc[-1] / joined.close_stock.iloc[0] - 1) * 100,
                    "spy_return_pct": (joined.close_spy.iloc[-1] / joined.close_spy.iloc[0] - 1) * 100,
                    "common_rows": len(joined),
                })
        except Exception as exc:
            failures.append({"ticker": ticker, "member": "benchmark", "error": str(exc)})

    pd.DataFrame(summaries).to_csv(OUTPUT / "strategy_summary.csv", index=False)
    pd.DataFrame(all_trades).to_csv(OUTPUT / "trades.csv", index=False)
    pd.DataFrame(benchmark_rows).to_csv(OUTPUT / "buy_hold_vs_spy.csv", index=False)
    pd.DataFrame(failures).to_csv(OUTPUT / "failures.csv", index=False)

    completed = pd.DataFrame(summaries)
    report = {
        "execution_enabled": False,
        "historical_news_gate": "UNAVAILABLE; BUY gate bypassed with explicit technical-only proxy",
        "price_adjustment_status": "Not verified from CSV metadata; corporate-action handling uncertain",
        "fill_model": "Signal at close t; execution at open t+1; open fills assumed; final open position liquidated at final close",
        "cost_assumption": f"{COST_BPS_PER_SIDE} bps per side, illustrative and configurable",
        "portfolio_note": "Per-ticker independent $100k simulations; do not sum returns as if capital were shared. This is a signal diagnostic, not the combined account portfolio.",
        "tickers_requested": sum(len(v) for v in MEMBERS.values()),
        "tickers_completed": len(summaries),
        "failures": failures,
        "mean_strategy_return_pct": float(completed["return_pct"].mean()) if len(completed) else None,
        "median_strategy_return_pct": float(completed["return_pct"].median()) if len(completed) else None,
        "mean_max_drawdown_pct": float(completed["max_drawdown_pct"].mean()) if len(completed) else None,
        "mean_closed_trades": float(completed["closed_trades"].mean()) if len(completed) else None,
    }
    (OUTPUT / "run_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\nSaved results to:", OUTPUT)
    print("Completed:", len(summaries), "/", report["tickers_requested"], "| failures:", len(failures))
    print("WARNING: technical-only proxy, not full historical strategy validation.")


if __name__ == "__main__":
    main()
