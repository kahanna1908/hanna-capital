"""
v3's brain: the trend signal, risk-parity sizing, and the daily accounting.

The accounting in step() is v2's, unchanged except that v3 has no beta hedge and no drawdown rule.
The same step() runs the live fund and the formula check, so the two can't drift apart.
"""

import math

import numpy as np
import pandas as pd

from v3 import config as C


# ----------------------------------------------------------------------------- signals
def signals(px: pd.DataFrame, rate: pd.Series) -> pd.DataFrame:
    """Average sign of each ETF's excess return over the lookbacks: -1, -1/3, +1/3 or +1 (NaN without history)."""
    tbill = (1 + rate / 252).cumprod()
    total = 0
    for n in C.LOOKBACKS:
        excess = (px[C.ASSETS] / px[C.ASSETS].shift(n)).sub(tbill / tbill.shift(n), axis=0)
        total = total + np.sign(excess)
    return total / len(C.LOOKBACKS)


def target_weights(sig: pd.Series, rets_hist: pd.DataFrame) -> pd.Series:
    """Equal risk per asset class, inverse-vol within a class, whole book scaled to the volatility target."""
    w = pd.Series(0.0, index=C.ASSETS)
    recent = rets_hist[C.ASSETS].iloc[-C.VOL_WINDOW:]
    vol = recent.std() * math.sqrt(252)
    ready = (recent.notna().sum() >= C.VOL_WINDOW) & (vol > 0) & sig.reindex(C.ASSETS).notna()

    active = [k for k, ts in C.CLASSES.items() if ready[ts].any()]
    for k in active:
        ts = [t for t in C.CLASSES[k] if ready[t]]
        for t in ts:
            w[t] = sig[t] / vol[t] / len(ts) / len(active)
    if w.abs().sum() == 0:
        return w

    cov = rets_hist[C.ASSETS].iloc[-C.COV_WINDOW:].fillna(0).cov().values * 252
    port_vol = math.sqrt(max(float(w.values @ cov @ w.values), 1e-12))
    scale = min(C.VOL_TARGET / port_vol, C.MAX_GROSS / w.abs().sum())
    return (w * scale).clip(-C.MAX_POSITION, C.MAX_POSITION)


# ----------------------------------------------------------------------------- fund state
def new_state() -> dict:
    return {
        "version": C.VERSION, "inception": None, "last_date": None, "cash": float(C.START_CAPITAL),
        "units": C.START_CAPITAL / C.START_NAV, "hwm": float(C.START_CAPITAL),
        "prev_equity": float(C.START_CAPITAL), "shares": {}, "avg_cost": {}, "last_rebal_month": None,
        "last_prices": {}, "totals": {"Management fees": 0.0, "Performance fees": 0.0,
                                      "Trading costs": 0.0, "Borrow costs": 0.0, "Interest earned": 0.0},
    }


def equity_of(state, prices) -> float:
    return state["cash"] + sum(q * prices[t] for t, q in state["shares"].items() if t in prices and not np.isnan(prices[t]))


def step(state: dict, d: pd.Timestamp, prices: pd.Series, sig_prev: pd.Series,
         rets_hist: pd.DataFrame, rate: float):
    """Process one trading day. Signals come from yesterday's close; trades fill at today's close.
    Returns (nav_row, trades)."""
    trades = []
    prices = prices.dropna()
    tot = state["totals"]
    if state["inception"] is None:
        state["inception"] = str(d.date())

    # performance fee crystallizes at the first close of a new year, on last year's gain over the high-water mark
    if state["last_date"] and pd.Timestamp(state["last_date"]).year != d.year:
        prev = state["prev_equity"]
        if prev > state["hwm"]:
            fee = (prev - state["hwm"]) * C.PERF_FEE
            state["cash"] -= fee
            tot["Performance fees"] += fee
            state["hwm"] = prev - fee
        else:
            state["hwm"] = max(state["hwm"], prev)

    gross_equity = equity_of(state, prices)
    gross_ret = gross_equity / state["prev_equity"] - 1

    # daily accruals: interest on cash (or on borrowing), borrow on shorts, management fee
    interest = state["cash"] * (rate if state["cash"] > 0 else rate + 0.01) / 252
    state["cash"] += interest
    tot["Interest earned"] += interest
    short_val = sum(-q * prices[t] for t, q in state["shares"].items() if q < 0 and t in prices)
    borrow = short_val * C.BORROW_FEE / 252
    state["cash"] -= borrow
    tot["Borrow costs"] += borrow
    equity = equity_of(state, prices)
    mgmt = equity * C.MGMT_FEE / 252
    state["cash"] -= mgmt
    tot["Management fees"] += mgmt
    equity -= mgmt

    # rebalance: at launch and on the first close of each month
    month = d.strftime("%Y-%m")
    reason = "Launch" if state["last_rebal_month"] is None else ("Monthly rebalance" if month != state["last_rebal_month"] else None)
    if reason and len(rets_hist) >= max(C.COV_WINDOW, C.VOL_WINDOW):
        w = target_weights(sig_prev, rets_hist)
        if w.abs().sum() > 0:
            state["last_rebal_month"] = month
            for t, wt in w.items():
                if t not in prices:
                    continue
                p = float(prices[t])
                cur = state["shares"].get(t, 0.0)
                tgt = wt * equity / p
                q = tgt - cur
                if abs(q * p) < C.MIN_TRADE * equity and not (tgt == 0 and cur != 0):
                    continue
                if abs(q) < 1e-9:
                    continue
                cost = abs(q * p) * C.COST_BPS / 1e4
                state["cash"] -= q * p + cost
                tot["Trading costs"] += cost
                update_cost_basis(state, t, cur, q, p)
                trades.append({"date": str(d.date()), "ticker": t, "side": side_of(cur, cur + q),
                               "qty": round(q, 2), "price": round(p, 2), "value": round(q * p, 2),
                               "cost": round(cost, 2), "reason": reason})
            equity = equity_of(state, prices)

    pos = {t: q * prices[t] for t, q in state["shares"].items() if t in prices}
    long_v = sum(v for v in pos.values() if v > 0)
    short_v = -sum(v for v in pos.values() if v < 0)
    state["last_prices"] = {t: round(float(p), 4) for t, p in prices.items()}
    state["prev_equity"] = equity
    state["last_date"] = str(d.date())
    row = {"date": str(d.date()), "nav": round(equity / state["units"], 4), "equity": round(equity, 2),
           "gross_return": round(gross_ret, 6), "long_exposure": round(long_v / equity, 4),
           "short_exposure": round(short_v / equity, 4), "net_exposure": round((long_v - short_v) / equity, 4),
           "spy": round(float(prices.get(C.BENCHMARK, np.nan)), 4), "tbill": round(rate, 5)}
    return row, trades


def update_cost_basis(state, t, cur, q, p):
    new = cur + q
    if abs(new) < 1e-9:
        state["shares"].pop(t, None)
        state["avg_cost"].pop(t, None)
        return
    if cur == 0 or (cur > 0) != (new > 0):                      # new or flipped position
        state["avg_cost"][t] = p
    elif abs(new) > abs(cur):                                    # adding to a position
        state["avg_cost"][t] = (state["avg_cost"][t] * abs(cur) + p * abs(q)) / abs(new)
    state["shares"][t] = new


def side_of(before: float, after: float) -> str:
    if after > before:
        return "BUY TO COVER" if before < 0 and after <= 0 else "BUY"
    return "SELL" if before > 0 and after >= 0 else "SELL SHORT"


# ----------------------------------------------------------------------------- data
def download(start: str):
    import yfinance as yf
    raw = yf.download(C.ASSETS + [C.RATE_TICKER], start=start, auto_adjust=True, progress=False)["Close"]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    rate = (raw[C.RATE_TICKER].ffill() / 100).fillna(0.0)
    px = raw[C.ASSETS].dropna(subset=[C.BENCHMARK])
    return px, rate.reindex(px.index).ffill().fillna(0.0)
