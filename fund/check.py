"""
Pre-launch formula check: run the exact live engine over history once, to make sure the
formula isn't broken before real-time trading starts. Settings were fixed before this was run.

    python -m fund.check            # real data
    python -m fund.check --demo     # random prices, tests the code only
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from fund import config as C
from fund import engine

SPLIT = "2020-01-01"


def simulated():
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2008-01-01", "2026-11-13")
    mkt = rng.normal(0.0004, 0.011, len(dates))
    data = {t: mkt * rng.uniform(0.7, 1.3) + rng.normal(0.0001, 0.008, len(dates)) for t in C.SECTORS}
    data[C.HEDGE] = mkt
    px = 100 * (1 + pd.DataFrame(data, index=dates)).cumprod()
    return px, pd.Series(0.02, index=dates)


def stats(r: pd.Series) -> dict:
    r = r.dropna()
    yrs = len(r) / 252
    eq = (1 + r).cumprod()
    sd = r.std()
    return {"cagr": float(eq.iloc[-1] ** (1 / yrs) - 1), "vol": float(sd * np.sqrt(252)),
            "sharpe": float(r.mean() / sd * np.sqrt(252)) if sd else None,
            "mdd": float((eq / eq.cummax() - 1).min())}


def main(demo):
    px, rate = simulated() if demo else engine.download("2007-01-01")
    sc, rets = engine.scores(px), px.pct_change()
    state, rows, n_trades = engine.new_state(), [], 0
    start = px.index.get_loc(px.index[px.index >= "2008-12-31"][0])
    for i in range(start, len(px)):
        row, trades = engine.step(state, px.index[i], px.iloc[i], sc.iloc[i - 1], rets.iloc[1:i], float(rate.iloc[i]))
        rows.append(row)
        n_trades += len(trades)
    nav = pd.DataFrame(rows).set_index("date")
    nav.index = pd.to_datetime(nav.index)
    net = nav["equity"].pct_change().dropna()
    spy = px[C.HEDGE].pct_change().reindex(net.index)
    out = {"demo": demo, "ran": pd.Timestamp.today().strftime("%Y-%m-%d"), "split": SPLIT,
           "from": str(nav.index[0].date()), "to": str(nav.index[-1].date()),
           "fund_in": stats(net[:SPLIT]), "fund_out": stats(net[SPLIT:]),
           "spy_in": stats(spy[:SPLIT]), "spy_out": stats(spy[SPLIT:]),
           "beta": float(net.cov(spy) / spy.var()), "trades_per_year": round(n_trades / (len(net) / 252)),
           "avg_gross": float((nav["long_exposure"] + nav["short_exposure"]).mean()),
           "totals": {k: round(v) for k, v in state["totals"].items()}}
    os.makedirs("data", exist_ok=True)
    with open(os.path.join("data", "check.json"), "w") as f:
        json.dump(out, f, indent=1)

    lines = [f"## Formula check {'(SIMULATED PRICES)' if demo else ''}",
             f"{out['from']} to {out['to']}, same engine as the live fund", "",
             "| | Annual return | Volatility | Sharpe | Max drawdown |", "|---|---|---|---|---|"]
    for k, lab in [("fund_in", f"Fund, before {SPLIT[:4]}"), ("fund_out", f"Fund, {SPLIT[:4]} on"),
                   ("spy_in", f"SPY, before {SPLIT[:4]}"), ("spy_out", f"SPY, {SPLIT[:4]} on")]:
        s = out[k]
        lines.append(f"| {lab} | {s['cagr']:.1%} | {s['vol']:.1%} | {s['sharpe']:.2f} | {s['mdd']:.1%} |")
    lines += ["", f"Beta to SPY {out['beta']:.2f} · {out['trades_per_year']} trades/yr · avg gross exposure {out['avg_gross']:.0%}",
              "", "Costs: " + ", ".join(f"{k} ${v:,.0f}" for k, v in out["totals"].items())]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    main(ap.parse_args().demo)
