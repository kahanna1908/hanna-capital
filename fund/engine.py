"""
The fund's brain: the trading formula and the daily accounting.

The same step() function runs the live fund (one day at a time, after each close)
and the formula check (looping over history), so the backtest and the live record
can never drift apart.
"""

import math

import numpy as np
import pandas as pd

from fund import config as C


# ----------------------------------------------------------------------------- signals
def zscore(df: pd.DataFrame) -> pd.DataFrame:
    """How far each sector is from the average sector that day, in standard deviations."""
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1), axis=0)


def scores(px: pd.DataFrame) -> pd.DataFrame:
    sec = px[C.SECTORS]
    momentum = sec.shift(C.MOM_SKIP) / sec.shift(C.MOM_LOOKBACK) - 1
    trend = sec / sec.rolling(C.TREND_SMA).mean() - 1
    return C.W_MOM * zscore(momentum) + C.W_TREND * zscore(trend)


def pick_book(score: pd.Series, longs: list, shorts: list):
    """Long the top N, short the bottom N, but keep existing holdings until they fall past EXIT_RANK."""
    s = score.dropna()
    if len(s) < 2 * C.N_SIDE:
        return [], []
    top = list(s.sort_values(ascending=False).index)
    bottom = top[::-1]
    rank_top = {t: i + 1 for i, t in enumerate(top)}
    rank_bot = {t: i + 1 for i, t in enumerate(bottom)}
    new_longs = [t for t in longs if t in rank_top and rank_top[t] <= C.EXIT_RANK][: C.N_SIDE]
    new_shorts = [t for t in shorts if t in rank_bot and rank_bot[t] <= C.EXIT_RANK and t not in new_longs][: C.N_SIDE]
    for t in top:
        if len(new_longs) >= C.N_SIDE:
            break
        if t not in new_longs and t not in new_shorts:
            new_longs.append(t)
    for t in bottom:
        if len(new_shorts) >= C.N_SIDE:
            break
        if t not in new_longs and t not in new_shorts:
            new_shorts.append(t)
    return new_longs, new_shorts


def target_weights(longs, shorts, rets_hist: pd.DataFrame, risk_scale: float) -> pd.Series:
    """Equal-dollar long/short book, scaled to the volatility target, beta-hedged with SPY."""
    cols = C.SECTORS + [C.HEDGE]
    w = pd.Series(0.0, index=cols)
    if not longs or not shorts:
        return w
    w[longs] = 1 / len(longs)
    w[shorts] = -1 / len(shorts)

    hist = rets_hist[cols].iloc[-C.BETA_WINDOW:]
    var_m = hist[C.HEDGE].var()
    beta = hist[C.SECTORS].apply(lambda c: c.cov(hist[C.HEDGE])) / var_m
    w[C.HEDGE] = -float((w[C.SECTORS] * beta.fillna(1.0)).sum())

    recent = rets_hist[cols].iloc[-C.COV_WINDOW:].fillna(0)
    cov = recent.cov().values * 252
    vol = math.sqrt(max(float(w.values @ cov @ w.values), 1e-12))
    scale = C.VOL_TARGET / vol
    scale = min(scale, C.MAX_GROSS / max(w.abs().sum(), 1e-9))
    w = (w * scale * risk_scale).clip(-C.MAX_POSITION, C.MAX_POSITION)
    return w


# ----------------------------------------------------------------------------- fund state
def new_state() -> dict:
    return {
        "inception": None, "last_date": None, "cash": float(C.START_CAPITAL),
        "units": C.START_CAPITAL / C.START_NAV, "hwm": float(C.START_CAPITAL),
        "peak_nav": C.START_NAV, "risk_scale": 1.0, "prev_equity": float(C.START_CAPITAL),
        "shares": {}, "avg_cost": {}, "longs": [], "shorts": [], "last_rebal_month": None,
        "last_prices": {}, "totals": {"Management fees": 0.0, "Performance fees": 0.0,
                                      "Trading costs": 0.0, "Borrow costs": 0.0, "Interest earned": 0.0},
    }


def equity_of(state, prices) -> float:
    return state["cash"] + sum(q * prices[t] for t, q in state["shares"].items() if t in prices and not np.isnan(prices[t]))


def step(state: dict, d: pd.Timestamp, prices: pd.Series, score_prev: pd.Series,
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

    # daily accruals: interest on cash, borrow on shorts, management fee
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

    # drawdown control
    nav = equity / state["units"]
    state["peak_nav"] = max(state["peak_nav"], nav)
    dd = nav / state["peak_nav"] - 1
    old_scale = state["risk_scale"]
    if dd <= C.DD_CUT:
        state["risk_scale"] = 0.5
    elif dd >= C.DD_RESET:
        state["risk_scale"] = 1.0

    # rebalance: at launch, on the first close of each month, or when the risk scale changes
    month = d.strftime("%Y-%m")
    reason = None
    if not state["shares"]:
        reason = "Launch"
    elif month != state["last_rebal_month"]:
        reason = "Monthly rebalance"
    elif state["risk_scale"] != old_scale:
        reason = "Risk cut" if state["risk_scale"] < old_scale else "Risk restored"

    if reason and len(rets_hist) >= C.BETA_WINDOW:
        longs, shorts = pick_book(score_prev, state["longs"], state["shorts"])
        w = target_weights(longs, shorts, rets_hist, state["risk_scale"])
        if longs:
            state["longs"], state["shorts"] = longs, shorts
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
           "spy": round(float(prices.get(C.HEDGE, np.nan)), 4), "tbill": round(rate, 5),
           "risk_scale": state["risk_scale"]}
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
    tickers = C.SECTORS + [C.HEDGE, C.RATE_TICKER]
    raw = yf.download(tickers, start=start, auto_adjust=True, progress=False)["Close"]
    raw.index = pd.to_datetime(raw.index).tz_localize(None)
    rate = (raw[C.RATE_TICKER].ffill() / 100).fillna(0.0)
    px = raw[C.SECTORS + [C.HEDGE]].dropna(subset=[C.HEDGE])
    return px, rate.reindex(px.index).ffill().fillna(0.0)
