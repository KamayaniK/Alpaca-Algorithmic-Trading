"""
Portfolio-level historical backtest for the three isolated paper-account universes.

Research only: no Alpaca client, network calls, or order submission.
Execution flags are deliberately disabled.

Run from the repository root:
    python backtest_portfolios.py

Inputs:
    *_daily_ohlcv_100.csv
    SPY_daily_ohlcv_100.csv

Outputs:
    reports/backtest_portfolios_20261014/account_summary.csv
    reports/backtest_portfolios_20261014/daily_equity.csv
    reports/backtest_portfolios_20261014/trades.csv
    reports/backtest_portfolios_20261014/run_summary.json

Important limitations:
- The project's existing signal function is replayed historically with the news gate
  set to True as a technical-only proxy. Historical news decisions are unavailable.
- Uses the OHLCV CSV close/open prices as supplied; adjusted-price status is not
  independently verified. Corporate actions/dividends may therefore distort results.
- Simulated fractional shares are allowed because the previously checked assets
  were reported fractionable; this is still only a backtest assumption.
- Signals are evaluated at close t and simulated at open t+1.
- 10 bps transaction cost is an illustrative assumption per side, not actual fees/slippage.
- All tickers and SPY are aligned to the common dates shared by all 36 tickers and SPY.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from indicators.technical_indicators import calculate_indicators
from trading_strategy import generate_signal

EXECUTION_ENABLED = False
LIVE_TRADING_ENABLED = False
PAPER_ORDER_SUBMISSION_ENABLED = False

INITIAL_CASH = 100_000.0
MAX_PLANNED_INVESTMENT = 95_000.0
MIN_CASH_RESERVE = 5_000.0
MAX_POSITION_VALUE = 13_000.0
TECH_CAP = 33_250.0
AI_HARDWARE_CAP = 23_750.0
COST_BPS_PER_SIDE = 10.0
COST_RATE = COST_BPS_PER_SIDE / 10_000.0

MEMBER_TICKERS = {
    "Mahi": ["SNDK", "AMD", "APP", "MRNA", "GOOGL", "AMZN", "JPM", "LLY", "META", "XOM", "PEP", "ABT"],
    "Ashima": ["SMCI", "MU", "MRVL", "WDC", "MSFT", "ETN", "GS", "ISRG", "CAT", "FCX", "PG", "CVX"],
    "Kamayani": ["HOOD", "COIN", "PLTR", "LITE", "TSLA", "AAPL", "NFLX", "GE", "AXP", "UNH", "DIS", "ABBV"],
}
TECH_TICKERS = frozenset(
    "SNDK AMD APP GOOGL AMZN META SMCI MU MRVL WDC MSFT HOOD COIN PLTR LITE TSLA AAPL NFLX".split()
)
AI_HARDWARE_TICKERS = frozenset("SNDK AMD SMCI MU MRVL WDC LITE".split())

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "reports" / "backtest_portfolios_20261014"


@dataclass
class Position:
    shares: float = 0.0
    cost_basis: float = 0.0


def load_ohlcv(ticker: str) -> pd.DataFrame:
    path = ROOT / f"{ticker}_daily_ohlcv_100.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing price file: {path}")
    df = pd.read_csv(path)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"{path.name} missing columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"]).copy()
    df = df.sort_values("timestamp").drop_duplicates("timestamp", keep="last")
    if (df[["open", "close"]] <= 0).any().any():
        raise ValueError(f"{path.name} contains non-positive open/close values")
    return df.reset_index(drop=True)


def exposure(positions: dict[str, Position], prices: dict[str, float], universe: list[str]) -> tuple[float, float, float]:
    values = {t: positions[t].shares * prices[t] for t in universe if t in prices}
    invested = sum(values.values())
    tech = sum(v for t, v in values.items() if t in TECH_TICKERS)
    ai = sum(v for t, v in values.items() if t in AI_HARDWARE_TICKERS)
    return invested, tech, ai


def run_account(member: str, universe: list[str], aligned: dict[str, pd.DataFrame], spy: pd.DataFrame):
    # Calculate the real project indicators once per ticker, using SPY as benchmark.
    indexed = {t: aligned[t].set_index("timestamp") for t in universe}
    spy_indexed = spy.set_index("timestamp")
    signal_frames: dict[str, pd.DataFrame] = {}
    for ticker in universe:
        stock_df = aligned[ticker].copy()
        spy_subset = spy[["timestamp", "close"]].copy()
        try:
            enriched = calculate_indicators(stock_df, spy_df=spy_subset)
        except TypeError:
            # Support projects whose function takes the benchmark as a positional argument.
            enriched = calculate_indicators(stock_df, spy_subset)
        if not isinstance(enriched, pd.DataFrame):
            raise TypeError("calculate_indicators must return a pandas DataFrame")
        signal_frames[ticker] = enriched.set_index("timestamp")

    dates = list(aligned[universe[0]]["timestamp"])
    cash = INITIAL_CASH
    positions = {t: Position() for t in universe}
    equity_rows = []
    trades = []
    skipped_buys = 0
    buy_signals = 0
    sell_signals = 0

    # First date establishes indicators only. On each later date, yesterday's
    # close signal is executed at today's open; holdings are marked at today's close.
    for i, day in enumerate(dates):
        opens = {t: float(indexed[t].loc[day, "open"]) for t in universe}
        closes = {t: float(indexed[t].loc[day, "close"]) for t in universe}

        if i > 0:
            signal_day = dates[i - 1]
            for ticker in universe:
                row = signal_frames[ticker].loc[signal_day]
                indicators = row.to_dict()
                indicators["news_check_passed"] = True
                indicators["severe_negative_news"] = False
                try:
                    result = generate_signal(indicators)
                except TypeError:
                    result = generate_signal(indicators, max_atr_pct=5.0)

                if isinstance(result, dict):
                    signal = str(result.get("signal", result.get("action", "HOLD"))).upper()
                    score = result.get("score")
                elif isinstance(result, (tuple, list)):
                    signal = str(result[0]).upper() if result else "HOLD"
                    score = result[1] if len(result) > 1 else None
                else:
                    signal = str(getattr(result, "signal", getattr(result, "action", result))).upper()
                    score = getattr(result, "score", None)
                signal = signal.split(".")[-1].strip()
                if signal not in {"BUY", "SELL", "HOLD"}:
                    signal = "HOLD"

                pos = positions[ticker]
                open_price = opens[ticker]
                if signal == "BUY":
                    buy_signals += 1
                    if pos.shares > 0:
                        continue
                    current_prices = closes.copy()
                    current_prices.update({t: opens[t] for t in universe})
                    invested, tech, ai = exposure(positions, current_prices, universe)
                    equity_at_open = cash + invested
                    target = min(MAX_POSITION_VALUE, max(0.0, MAX_PLANNED_INVESTMENT - invested))
                    target = min(target, max(0.0, cash - MIN_CASH_RESERVE))
                    if ticker in TECH_TICKERS:
                        target = min(target, max(0.0, TECH_CAP - tech))
                    if ticker in AI_HARDWARE_TICKERS:
                        target = min(target, max(0.0, AI_HARDWARE_CAP - ai))
                    target = min(target, max(0.0, equity_at_open - MIN_CASH_RESERVE))
                    shares = target / open_price if open_price > 0 else 0.0
                    notional = shares * open_price
                    if notional < 1.0:
                        skipped_buys += 1
                        continue
                    cost = notional * COST_RATE
                    if cash - notional - cost < MIN_CASH_RESERVE - 1e-6:
                        affordable = max(0.0, cash - MIN_CASH_RESERVE) / (1.0 + COST_RATE)
                        notional = min(notional, affordable)
                        shares = notional / open_price
                        cost = notional * COST_RATE
                    # Re-check caps after affordability adjustment.
                    if (notional < 1.0 or invested + notional > MAX_PLANNED_INVESTMENT + 1e-6
                        or (ticker in TECH_TICKERS and tech + notional > TECH_CAP + 1e-6)
                        or (ticker in AI_HARDWARE_TICKERS and ai + notional > AI_HARDWARE_CAP + 1e-6)
                        or notional > MAX_POSITION_VALUE + 1e-6):
                        skipped_buys += 1
                        continue
                    cash -= notional + cost
                    pos.shares = shares
                    pos.cost_basis = notional + cost
                    trades.append({
                        "member": member, "date": day.isoformat(), "ticker": ticker,
                        "side": "BUY", "shares": shares, "price": open_price,
                        "notional": notional, "cost": cost, "signal_date": signal_day.isoformat(),
                        "signal": signal, "signal_score": score,
                    })
                elif signal == "SELL":
                    sell_signals += 1
                    if pos.shares <= 0:
                        continue
                    shares = pos.shares
                    notional = shares * open_price
                    cost = notional * COST_RATE
                    cash += notional - cost
                    trades.append({
                        "member": member, "date": day.isoformat(), "ticker": ticker,
                        "side": "SELL", "shares": shares, "price": open_price,
                        "notional": notional, "cost": cost, "signal_date": signal_day.isoformat(),
                        "signal": signal, "signal_score": score,
                    })
                    pos.shares = 0.0
                    pos.cost_basis = 0.0

        position_values = {t: positions[t].shares * closes[t] for t in universe}
        invested = sum(position_values.values())
        tech = sum(v for t, v in position_values.items() if t in TECH_TICKERS)
        ai = sum(v for t, v in position_values.items() if t in AI_HARDWARE_TICKERS)
        equity = cash + invested
        equity_rows.append({
            "member": member, "date": day.isoformat(), "cash": cash,
            "market_value": invested, "equity": equity,
            "return_pct": (equity / INITIAL_CASH - 1.0) * 100.0,
            "technology_exposure": tech, "ai_hardware_exposure": ai,
            "position_count": sum(1 for p in positions.values() if p.shares > 0),
            "planned_investment_limit": MAX_PLANNED_INVESTMENT,
            "cash_reserve_limit": MIN_CASH_RESERVE,
        })

    # Liquidate remaining positions at final close, charge exit cost, and use this
    # as the terminal equity so strategy returns include a final exit cost.
    final_day = dates[-1]
    final_closes = {t: float(indexed[t].loc[final_day, "close"]) for t in universe}
    for ticker, pos in positions.items():
        if pos.shares <= 0:
            continue
        notional = pos.shares * final_closes[ticker]
        cost = notional * COST_RATE
        cash += notional - cost
        trades.append({
            "member": member, "date": final_day.isoformat(), "ticker": ticker,
            "side": "FINAL_LIQUIDATION", "shares": pos.shares, "price": final_closes[ticker],
            "notional": notional, "cost": cost, "signal_date": "",
            "signal": "FORCED_END_OF_TEST", "signal_score": "",
        })
        pos.shares = 0.0

    equity_rows[-1]["cash"] = cash
    equity_rows[-1]["market_value"] = 0.0
    equity_rows[-1]["equity"] = cash
    equity_rows[-1]["return_pct"] = (cash / INITIAL_CASH - 1.0) * 100.0
    equity_series = pd.Series([r["equity"] for r in equity_rows], dtype=float)
    peaks = equity_series.cummax()
    drawdowns = (equity_series / peaks - 1.0) * 100.0
    for row, dd in zip(equity_rows, drawdowns):
        row["drawdown_pct"] = float(dd)

    total_costs = sum(float(t["cost"]) for t in trades)
    closed_trades = sum(1 for t in trades if t["side"] in {"SELL", "FINAL_LIQUIDATION"})
    spy_start = float(spy.loc[spy["timestamp"] == dates[0], "close"].iloc[0])
    spy_end = float(spy.loc[spy["timestamp"] == dates[-1], "close"].iloc[0])
    spy_return = (spy_end / spy_start - 1.0) * 100.0
    summary = {
        "member": member,
        "initial_equity": INITIAL_CASH,
        "final_equity": cash,
        "strategy_return_pct": (cash / INITIAL_CASH - 1.0) * 100.0,
        "spy_buy_hold_return_pct": spy_return,
        "excess_return_vs_spy_pct_points": (cash / INITIAL_CASH - 1.0) * 100.0 - spy_return,
        "max_drawdown_pct": float(drawdowns.min()),
        "total_transaction_costs_usd": total_costs,
        "buy_entries": sum(1 for t in trades if t["side"] == "BUY"),
        "closed_trades": closed_trades,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "skipped_buys_for_constraints": skipped_buys,
        "test_start": dates[0].isoformat(),
        "test_end": dates[-1].isoformat(),
        "ticker_count": len(universe),
        "cost_assumption_bps_per_side": COST_BPS_PER_SIDE,
        "news_gate": "technical-only proxy; historical news decisions unavailable",
        "adjusted_prices_verified": False,
        "execution_enabled": EXECUTION_ENABLED,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "paper_order_submission_enabled": PAPER_ORDER_SUBMISSION_ENABLED,
    }
    return summary, equity_rows, trades


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_tickers = sorted(set(t for universe in MEMBER_TICKERS.values() for t in universe))
    failures = []
    data: dict[str, pd.DataFrame] = {}
    for ticker in all_tickers + ["SPY"]:
        try:
            data[ticker] = load_ohlcv(ticker)
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})

    if failures:
        pd.DataFrame(failures).to_csv(OUTPUT_DIR / "failures.csv", index=False)
        print("Missing/invalid input files; see failures.csv:")
        print(pd.DataFrame(failures).to_string(index=False))
        return 1

    # Use the common intersection across all stocks and SPY to avoid mismatched periods.
    common_dates = set(data["SPY"]["timestamp"])
    for ticker in all_tickers:
        common_dates &= set(data[ticker]["timestamp"])
    common_dates = sorted(common_dates)
    if len(common_dates) < 60:
        raise RuntimeError(f"Only {len(common_dates)} common dates; refusing unreliable backtest.")
    for ticker in all_tickers + ["SPY"]:
        data[ticker] = data[ticker][data[ticker]["timestamp"].isin(common_dates)].reset_index(drop=True)

    summaries, daily_rows, trade_rows = [], [], []
    for member, universe in MEMBER_TICKERS.items():
        summary, equity_rows, trades = run_account(member, universe, data, data["SPY"])
        summaries.append(summary)
        daily_rows.extend(equity_rows)
        trade_rows.extend(trades)

    pd.DataFrame(summaries).to_csv(OUTPUT_DIR / "account_summary.csv", index=False)
    pd.DataFrame(daily_rows).to_csv(OUTPUT_DIR / "daily_equity.csv", index=False)
    pd.DataFrame(trade_rows).to_csv(OUTPUT_DIR / "trades.csv", index=False)

    run_summary = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "accounts_completed": len(summaries),
        "tickers_processed": len(all_tickers),
        "common_date_count": len(common_dates),
        "common_start": common_dates[0].isoformat(),
        "common_end": common_dates[-1].isoformat(),
        "initial_equity_per_account": INITIAL_CASH,
        "max_planned_investment": MAX_PLANNED_INVESTMENT,
        "minimum_cash_reserve": MIN_CASH_RESERVE,
        "max_single_position": MAX_POSITION_VALUE,
        "technology_exposure_cap": TECH_CAP,
        "ai_hardware_exposure_cap": AI_HARDWARE_CAP,
        "transaction_cost_bps_per_side": COST_BPS_PER_SIDE,
        "execution_enabled": EXECUTION_ENABLED,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "paper_order_submission_enabled": PAPER_ORDER_SUBMISSION_ENABLED,
        "limitations": [
            "Historical news gate replaced with a technical-only proxy; historical news decisions unavailable.",
            "Adjusted-price status is unverified; dividends and corporate actions may distort results.",
            "Open-price fills and 10 bps per-side costs are simulated assumptions, not actual fills.",
            "Fractional shares are simulated.",
            "All stocks and SPY use the common date intersection.",
            "Results are historical simulation, not evidence of future profitability.",
        ],
    }
    (OUTPUT_DIR / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")

    print(f"Backtest complete: {len(summaries)} accounts, {len(all_tickers)} tickers, {len(common_dates)} aligned dates.")
    print(f"Output directory: {OUTPUT_DIR}")
    print(pd.DataFrame(summaries)[[
        "member", "strategy_return_pct", "spy_buy_hold_return_pct",
        "excess_return_vs_spy_pct_points", "max_drawdown_pct",
        "total_transaction_costs_usd", "buy_entries", "closed_trades",
        "skipped_buys_for_constraints"
    ]].round(2).to_string(index=False))
    print("\nExecution remains disabled; this script has no broker/order-submission code.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
