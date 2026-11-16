"""
v3 trade journal: the reasoning behind each rebalance, written from the same numbers the formula used
that evening and committed with the trades. Logging only: nothing here changes a trade.
"""

import json
import math
import os

import pandas as pd

from fund.journal import kind
from v3 import config as C

SIG_TEXT = {1.0: "+1 (all three windows up)", 1 / 3: "+⅓ (two of three up)",
            -1 / 3: "−⅓ (two of three down)", -1.0: "−1 (all three down)"}


def sig_text(s):
    for k, v in SIG_TEXT.items():
        if abs(s - k) < 1e-6:
            return v
    return f"{s:+.2f}"


def entry(d, px: pd.DataFrame, i: int, sig: pd.DataFrame, rate: pd.Series, rets: pd.DataFrame,
          trades: list, state: dict, row: dict):
    if not trades:
        return None
    tbill = (1 + rate / 252).cumprod()
    prev = px[C.ASSETS].iloc[:i]                                    # everything up to yesterday's close
    j = i - 1
    excess = {n: prev.iloc[-1] / prev.iloc[-1 - n] - tbill.iloc[j] / tbill.iloc[j - n] for n in C.LOOKBACKS}
    s = sig.iloc[j]
    vol = rets[C.ASSETS].iloc[1:i].iloc[-C.VOL_WINDOW:].std() * math.sqrt(252)
    cls = {t: k for k, ts in C.CLASSES.items() for t in ts}
    equity = row["equity"]
    px_today = px.iloc[i]
    weight = {t: q * px_today[t] / equity for t, q in state["shares"].items()}
    labels = [f"{n // 21}m" for n in C.LOOKBACKS]

    def facts(t):
        ex = ", ".join(f"{excess[n][t]:+.1%} ({lab})" for n, lab in zip(C.LOOKBACKS, labels))
        return f"return vs T-bills {ex}; signal {sig_text(s[t])}"

    out = []
    for tr in trades:
        t, p = tr["ticker"], tr["price"]
        after = state["shares"].get(t, 0.0)
        before = after - tr["qty"]
        k = kind(before, after)
        w0, w1 = before * p / equity, after * p / equity
        sizing = (f"{cls[t]} get ¼ of the fund's risk, split across their ETFs by volatility "
                  f"({t} {vol[t]:.0%} a year)")
        if pd.isna(s[t]):
            why = "No usable trend signal (not enough price history), so the position is closed."
        elif k in ("Open long", "Open short"):
            why = (f"{'Uptrend' if s[t] > 0 else 'Downtrend'}: {facts(t)}. Sized at {w1:+.1%} of NAV: {sizing}.")
        elif k.startswith("Flip"):
            why = f"Trend reversed: {facts(t)}. Now {w1:+.1%} of NAV."
        elif k.startswith("Close"):
            why = f"Signal no longer supports the position: {facts(t)}."
        else:
            why = (f"Trend unchanged ({'up' if s[t] > 0 else 'down'}; {facts(t)}). Resized from {w0:+.1%} to "
                   f"{w1:+.1%} of NAV as volatilities and correlations shifted, to stay at the "
                   f"{C.VOL_TARGET:.0%} volatility target.")
        out.append({"ticker": t, "name": C.NAMES.get(t, t), "action": k, "side": tr["side"], "qty": tr["qty"],
                    "price": p, "value": tr["value"], "w_before": round(w0, 4), "w_after": round(w1, 4), "why": why})

    by_class = {k: sum(weight.get(t, 0) for t in ts) for k, ts in C.CLASSES.items()}
    n_long = sum(1 for w in weight.values() if w > 0)
    n_short = sum(1 for w in weight.values() if w < 0)
    summary = (f"{tr['reason']}. {n_long} longs and {n_short} shorts. Net exposure by asset class: "
               + ", ".join(f"{k} {v:+.0%}" for k, v in by_class.items())
               + f". Gross {row['long_exposure'] + row['short_exposure']:.0%}, net {row['net_exposure']:+.0%}. "
               f"Signals are from the {prev.index[-1].date()} close; fills at the {d.date()} close.")
    table = []
    for t in C.ASSETS:
        if pd.isna(s[t]):
            continue
        w = weight.get(t, 0.0)
        table.append([t, cls[t]] + [f"{excess[n][t]:+.1%}" for n in C.LOOKBACKS]
                     + [sig_text(s[t]).split(" ")[0], f"{w:+.1%}"])
    return {"date": str(d.date()), "reason": tr["reason"], "summary": summary, "trades": out,
            "signalTitle": "Trend signals at the prior close",
            "signalCols": ["ETF", "Class"] + [f"vs T-bills {lab}" for lab in labels] + ["Signal", "Weight"],
            "signals": table}


def append(path: str, e: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(e) + "\n")
