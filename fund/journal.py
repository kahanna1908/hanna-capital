"""
v2 trade journal: the reasoning behind each rebalance, written from the same numbers the formula used
that evening and committed with the trades. Logging only: nothing here changes a trade.
"""

import json
import os

import pandas as pd

from fund import config as C


def kind(before: float, after: float) -> str:
    if abs(before) < 0.5:
        return "Open long" if after > 0 else "Open short"
    if abs(after) < 0.5:
        return "Close long" if before > 0 else "Close short"
    if (before > 0) != (after > 0):
        return "Flip to long" if after > 0 else "Flip to short"
    return "Add" if abs(after) > abs(before) else "Trim"


def entry(d, px: pd.DataFrame, i: int, sc: pd.DataFrame, trades: list, state: dict, row: dict):
    if not trades:
        return None
    prev = px[C.SECTORS].iloc[:i]                                   # everything up to yesterday's close
    mom = prev.iloc[-1 - C.MOM_SKIP] / prev.iloc[-1 - C.MOM_LOOKBACK] - 1
    trend = prev.iloc[-1] / prev.iloc[-C.TREND_SMA:].mean() - 1
    score = sc.iloc[i - 1].dropna()
    n = len(score)
    rank = score.rank(ascending=False).astype(int)
    equity = row["equity"]
    px_today = px.iloc[i]
    weight = {t: q * px_today[t] / equity for t, q in state["shares"].items()}
    risk_note = " with risk halved by the drawdown rule" if state["risk_scale"] < 1 else ""

    out = []
    for tr in trades:
        t, p = tr["ticker"], tr["price"]
        after = state["shares"].get(t, 0.0)
        before = after - tr["qty"]
        k = kind(before, after)
        w0, w1 = before * p / equity, after * p / equity
        if t == C.HEDGE:
            why = (f"Market hedge. The six sector positions together still move with the stock market, so the fund "
                   f"holds SPY at {w1:+.1%} of NAV to bring its net beta to about zero.")
        else:
            r, s = rank.get(t), score.get(t)
            facts = f"score {s:+.2f}: 12-month momentum {mom[t]:+.1%}, {trend[t]:+.1%} vs its 200-day average"
            if k == "Open long":
                why = f"Ranked #{r} of {n} ({facts}). The top {C.N_SIDE} sectors go long."
            elif k == "Open short":
                why = f"Ranked #{r} of {n} ({facts}). The bottom {C.N_SIDE} sectors go short."
            elif k == "Close long":
                why = (f"Fell to #{r} of {n} ({facts}), past the exit buffer at rank {C.EXIT_RANK}, so the long is closed."
                       if r > C.EXIT_RANK else f"Replaced by a higher-ranked sector (now #{r} of {n}).")
            elif k == "Close short":
                rb = n + 1 - r
                why = (f"Rose to #{rb} from the bottom ({facts}), past the exit buffer at rank {C.EXIT_RANK}, so the short is covered."
                       if rb > C.EXIT_RANK else f"Replaced by a lower-ranked sector (now #{r} of {n}).")
            elif k.startswith("Flip"):
                why = f"Switched sides: now ranked #{r} of {n} ({facts})."
            else:
                why = (f"Still held, ranked #{r} of {n}. Resized from {w0:+.1%} to {w1:+.1%} of NAV to keep equal "
                       f"weights at the {C.VOL_TARGET:.0%} volatility target{risk_note}.")
        out.append({"ticker": t, "name": C.NAMES.get(t, t), "action": k, "side": tr["side"], "qty": tr["qty"],
                    "price": p, "value": tr["value"], "w_before": round(w0, 4), "w_after": round(w1, 4), "why": why})

    longs = [t for t in C.SECTORS if weight.get(t, 0) > 0]
    shorts = [t for t in C.SECTORS if weight.get(t, 0) < 0]
    summary = (f"{tr['reason']}. Long {', '.join(longs) or 'none'}; short {', '.join(shorts) or 'none'}; "
               f"SPY hedge {weight.get(C.HEDGE, 0):+.1%} of NAV. Gross exposure "
               f"{row['long_exposure'] + row['short_exposure']:.0%}, net {row['net_exposure']:+.0%}{risk_note}. "
               f"Signals are from the {prev.index[-1].date()} close; fills at the {d.date()} close.")
    table = []
    for t in rank.sort_values().index:
        side = "Long" if weight.get(t, 0) > 0 else "Short" if weight.get(t, 0) < 0 else "—"
        table.append([f"#{rank[t]}", t, f"{score[t]:+.2f}", f"{mom[t]:+.1%}", f"{trend[t]:+.1%}", side])
    return {"date": str(d.date()), "reason": tr["reason"], "summary": summary, "trades": out,
            "signalTitle": "Sector ranking at the prior close",
            "signalCols": ["Rank", "ETF", "Score", "12-1m momentum", "vs 200-day", "Book"], "signals": table}


def append(path: str, e: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(e) + "\n")
