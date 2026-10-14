import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORT_DIR = ROOT / "reports" / "backtest_portfolios_20261014"
DAILY = REPORT_DIR / "daily_equity.csv"
TRADES = REPORT_DIR / "trades.csv"
SUMMARY = REPORT_DIR / "account_summary.csv"

def read_csv(path):
    if not path.is_file():
        raise SystemExit(f"Missing required file: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if not reader.fieldnames:
            raise SystemExit(f"No header found in {path}")
        return reader.fieldnames, rows

def pick(row, *names):
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    raise KeyError(f"Expected one of {names}; actual columns: {list(row)}")

# 1) Risk drift audit
daily_fields, daily_rows = read_csv(DAILY)
risk = defaultdict(lambda: {
    "days": 0, "cash_breach_days": 0, "investment_breach_days": 0,
    "technology_breach_days": 0, "ai_hardware_breach_days": 0,
    "min_cash": float("inf"), "max_market_value": 0.0,
    "max_technology_exposure": 0.0, "max_ai_hardware_exposure": 0.0
})
for row in daily_rows:
    member = pick(row, "member", "account")
    cash = float(pick(row, "cash", "cash_balance"))
    market = float(pick(row, "market_value", "positions_value", "position_value"))
    tech = float(pick(row, "technology_exposure", "tech_exposure"))
    ai = float(pick(row, "ai_hardware_exposure", "ai_exposure"))
    d = risk[member]
    d["days"] += 1
    d["cash_breach_days"] += cash < 5000 - 0.01
    d["investment_breach_days"] += market > 95000 + 0.01
    d["technology_breach_days"] += tech > 33250 + 0.01
    d["ai_hardware_breach_days"] += ai > 23750 + 0.01
    d["min_cash"] = min(d["min_cash"], cash)
    d["max_market_value"] = max(d["max_market_value"], market)
    d["max_technology_exposure"] = max(d["max_technology_exposure"], tech)
    d["max_ai_hardware_exposure"] = max(d["max_ai_hardware_exposure"], ai)

risk_path = REPORT_DIR / "risk_breach_audit.csv"
risk_cols = ["member", "days", "cash_breach_days", "investment_breach_days",
             "technology_breach_days", "ai_hardware_breach_days", "min_cash",
             "max_market_value", "max_technology_exposure", "max_ai_hardware_exposure"]
with risk_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=risk_cols)
    w.writeheader()
    for member in sorted(risk):
        d = risk[member]
        w.writerow({"member": member, **{
            k: (round(d[k], 2) if k in {"min_cash", "max_market_value", "max_technology_exposure", "max_ai_hardware_exposure"} else d[k])
            for k in risk_cols if k != "member"
        }})

# 2) Approximate fixed-trade-path cost sensitivity.
# Existing trade costs are already reflected in final equity. Estimate incremental cost
# only, keeping the original trade path fixed; this is not a full strategy rerun.
_, summary_rows = read_csv(SUMMARY)
_, trade_rows = read_csv(TRADES)
final_equity = {r["member"]: float(r["final_equity"]) for r in summary_rows}
initial_equity = {r["member"]: float(r["initial_equity"]) for r in summary_rows}
notional_by_member = defaultdict(float)
for row in trade_rows:
    notional_by_member[row["member"]] += abs(float(row["notional"]))

cost_path = REPORT_DIR / "cost_sensitivity_estimate.csv"
cost_cols = ["member", "assumed_cost_bps_per_side", "baseline_cost_bps_per_side",
             "total_trade_notional", "estimated_incremental_cost", "estimated_final_equity",
             "estimated_return_pct", "method_note"]
with cost_path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cost_cols)
    w.writeheader()
    for member in sorted(final_equity):
        for bps in (10, 20, 30, 50):
            extra = notional_by_member[member] * (bps - 10) / 10000.0
            est_equity = final_equity[member] - extra
            w.writerow({
                "member": member,
                "assumed_cost_bps_per_side": bps,
                "baseline_cost_bps_per_side": 10,
                "total_trade_notional": round(notional_by_member[member], 2),
                "estimated_incremental_cost": round(extra, 2),
                "estimated_final_equity": round(est_equity, 2),
                "estimated_return_pct": round((est_equity / initial_equity[member] - 1) * 100, 4),
                "method_note": "Fixed trade path; incremental costs only; does not resimulate sizing/signals"
            })

print("Risk audit:", risk_path)
print("Cost sensitivity estimate:", cost_path)
print("\nRisk audit:")
for r in csv.DictReader(risk_path.open(newline="", encoding="utf-8")):
    print(r)
print("\nCost sensitivity:")
for r in csv.DictReader(cost_path.open(newline="", encoding="utf-8")):
    print(r)
