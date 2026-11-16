"""
v3 pre-launch formula check: run the exact live engine over history once, to make sure the
formula isn't broken. Settings were fixed in v3/DESIGN.md before this was run.

    python -m v3.check            # real data
    python -m v3.check --demo     # random prices, tests the code only
"""

import argparse
import json
import os

import numpy as np
import pandas as pd

from v3 import config as C
from v3 import engine

SPLIT = "2020-01-01"


def simulated():
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2006-01-01", "2026-11-13")
    mkt = rng.normal(0.0003, 0.011, len(dates))
    data = {}
    for t in C.ASSETS:
        drift = rng.normal(0, 0.0004)                 # some assets trend, so the signal has something to find
        data[t] = mkt * rng.uniform(-0.3, 1.2) + rng.normal(drift, rng.uniform(0.003, 0.015), len(dates))
    px = 100 * (1 + pd.DataFrame(data, index=dates)).cumprod()
    px.loc[:"2007-12-31", "EMB"] = np.nan             # one late-listing ETF, like the real data
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
    px, rate = simulated() if demo else engine.download("2005-01-01")
    px = px.ffill(limit=5)                            # bridge rare one-day data gaps; never fills before listing
    sig, rets = engine.signals(px, rate), px.pct_change(fill_method=None)
    state, rows, n_trades = engine.new_state(), [], 0
    start = px.index.get_loc(px.index[px.index >= "2008-12-31"][0])
    max_gross = 0.0
    for i in range(start, len(px)):
        row, trades = engine.step(state, px.index[i], px.iloc[i], sig.iloc[i - 1], rets.iloc[1:i], float(rate.iloc[i]))
        rows.append(row)
        n_trades += len(trades)
        max_gross = max(max_gross, row["long_exposure"] + row["short_exposure"])
    nav = pd.DataFrame(rows).set_index("date")
    nav.index = pd.to_datetime(nav.index)
    net = nav["equity"].pct_change().dropna()
    spy = px[C.BENCHMARK].pct_change(fill_method=None).reindex(net.index)
    yearly = (1 + net).groupby(net.index.year).prod() - 1
    out = {"version": C.VERSION, "demo": demo, "ran": pd.Timestamp.today().strftime("%Y-%m-%d"), "split": SPLIT,
           "from": str(nav.index[0].date()), "to": str(nav.index[-1].date()),
           "fund_in": stats(net[:SPLIT]), "fund_out": stats(net[SPLIT:]),
           "spy_in": stats(spy[:SPLIT]), "spy_out": stats(spy[SPLIT:]),
           "beta": float(net.cov(spy) / spy.var()), "corr": float(net.corr(spy)),
           "trades_per_year": round(n_trades / (len(net) / 252)),
           "avg_gross": float((nav["long_exposure"] + nav["short_exposure"]).mean()), "max_gross": max_gross,
           "avg_net": float(nav["net_exposure"].mean()),
           "years": {str(y): round(float(v), 4) for y, v in yearly.items()},
           "totals": {k: round(v) for k, v in state["totals"].items()}}
    os.makedirs(C.DATA_DIR, exist_ok=True)
    with open(os.path.join(C.DATA_DIR, "check.json"), "w") as f:
        json.dump(out, f, indent=1)

    lines = [f"## v3 formula check {'(SIMULATED PRICES)' if demo else ''}",
             f"{out['from']} to {out['to']}, same engine as the live fund", "",
             "| | Annual return | Volatility | Sharpe | Max drawdown |", "|---|---|---|---|---|"]
    for k, lab in [("fund_in", f"Fund, before {SPLIT[:4]}"), ("fund_out", f"Fund, {SPLIT[:4]} on"),
                   ("spy_in", f"SPY, before {SPLIT[:4]}"), ("spy_out", f"SPY, {SPLIT[:4]} on")]:
        s = out[k]
        lines.append(f"| {lab} | {s['cagr']:.1%} | {s['vol']:.1%} | {s['sharpe']:.2f} | {s['mdd']:.1%} |")
    lines += ["", f"Beta to SPY {out['beta']:.2f} · correlation {out['corr']:.2f} · {out['trades_per_year']} trades/yr · "
              f"avg gross {out['avg_gross']:.0%} (max {out['max_gross']:.0%}) · avg net {out['avg_net']:.0%}",
              "", "By year: " + ", ".join(f"{y} {v:+.1%}" for y, v in out["years"].items()),
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
