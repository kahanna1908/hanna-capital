"""
Runs v3 after every market close (GitHub Actions does this automatically).
Processes any final closes since the last run that are on or after LAUNCH_DATE, then saves the books.

    python -m v3.run_daily
"""

import csv
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from v3 import config as C
from v3 import engine

STATE, NAV, TRADES = (os.path.join(C.DATA_DIR, f) for f in ("state.json", "nav.csv", "trades.csv"))
NAV_COLS = ["date", "nav", "equity", "gross_return", "long_exposure", "short_exposure",
            "net_exposure", "spy", "tbill"]
TRADE_COLS = ["date", "ticker", "side", "qty", "price", "value", "cost", "reason"]


def append(path, cols, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    if not C.LAUNCH_DATE:
        print("v3 has no launch date yet; nothing to do.")
        return
    os.makedirs(C.DATA_DIR, exist_ok=True)
    state = json.load(open(STATE)) if os.path.exists(STATE) else engine.new_state()
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    px, rate = engine.download(start)
    complete = px[C.ASSETS].notna().all(axis=1)       # a day is booked only once every ETF has a close
    px = px.ffill(limit=5)                            # same gap bridging as the formula check
    sig = engine.signals(px, rate)
    rets = px.pct_change(fill_method=None)

    # only book final closes: today's bar counts once the market has been closed for 30 minutes
    now = datetime.now(ZoneInfo("America/New_York"))
    today = pd.Timestamp(now.date())
    closed = now.hour * 60 + now.minute >= 16 * 60 + 30

    launch = pd.Timestamp(C.LAUNCH_DATE)
    after = pd.Timestamp(state["last_date"]) if state["last_date"] else launch - pd.Timedelta(days=1)
    todo = [d for d in px.index if d > after and d >= launch and (d < today or (d == today and closed))]
    if not todo:
        print(f"Nothing to do. Latest close in data: {px.index[-1].date()}, v3 launches {C.LAUNCH_DATE}.")
        return
    for d in todo:
        if not complete[d]:
            missing = [t for t in C.ASSETS if pd.isna(px.at[d, t])]
            print(f"{d.date()}: no close yet for {', '.join(missing)}; stopping, the next run retries.")
            break
        i = px.index.get_loc(d)
        row, trades = engine.step(state, d, px.iloc[i], sig.iloc[i - 1], rets.iloc[1:i], float(rate.iloc[i]))
        append(NAV, NAV_COLS, [row])
        append(TRADES, TRADE_COLS, trades)
        print(f"{row['date']}  NAV ${row['nav']:.4f}  long {row['long_exposure']:.0%}  "
              f"short {row['short_exposure']:.0%}  trades {len(trades)}")
    with open(STATE, "w") as f:
        json.dump(state, f, indent=1)


if __name__ == "__main__":
    main()
