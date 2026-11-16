"""
Runs after every market close (GitHub Actions does this automatically).
Processes any closes since the last run that are on or after LAUNCH_DATE, then saves the books.

    python -m fund.run_daily
"""

import csv
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from fund import config as C
from fund import engine

DATA = "data"
STATE, NAV, TRADES, JOURNAL = (os.path.join(DATA, f) for f in ("state.json", "nav.csv", "trades.csv", "journal.jsonl"))
NAV_COLS = ["date", "nav", "equity", "gross_return", "long_exposure", "short_exposure",
            "net_exposure", "spy", "tbill", "risk_scale"]
TRADE_COLS = ["date", "ticker", "side", "qty", "price", "value", "cost", "reason"]


def append(path, cols, rows):
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerows(rows)


def main():
    os.makedirs(DATA, exist_ok=True)
    state = json.load(open(STATE)) if os.path.exists(STATE) else engine.new_state()
    start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
    px, rate = engine.download(start)
    sc = engine.scores(px)
    rets = px.pct_change()

    # only book final closes: today's bar counts once the market has been closed for 30 minutes
    now = datetime.now(ZoneInfo("America/New_York"))
    today = pd.Timestamp(now.date())
    closed = now.hour * 60 + now.minute >= 16 * 60 + 30
    complete = px[C.SECTORS + [C.HEDGE]].notna().all(axis=1)

    after = pd.Timestamp(state["last_date"]) if state["last_date"] else pd.Timestamp(C.LAUNCH_DATE) - pd.Timedelta(days=1)
    todo = [d for d in px.index if d > after and d >= pd.Timestamp(C.LAUNCH_DATE)
            and (d < today or (d == today and closed))]
    if not todo:
        print(f"Nothing to do. Latest close in data: {px.index[-1].date()}, fund launches {C.LAUNCH_DATE}.")
        return
    for d in todo:
        if not complete[d]:
            missing = [t for t in C.SECTORS + [C.HEDGE] if pd.isna(px.at[d, t])]
            print(f"{d.date()}: no close yet for {', '.join(missing)}; stopping, the next run retries.")
            break
        i = px.index.get_loc(d)
        row, trades = engine.step(state, d, px.iloc[i], sc.iloc[i - 1], rets.iloc[1:i], float(rate.iloc[i]))
        append(NAV, NAV_COLS, [row])
        append(TRADES, TRADE_COLS, trades)
        try:                                                   # the journal must never block the books
            from fund import journal
            e = journal.entry(d, px, i, sc, trades, state, row)
            if e:
                journal.append(JOURNAL, e)
        except Exception as ex:
            print(f"Journal skipped for {d.date()}: {ex!r}")
        print(f"{row['date']}  NAV ${row['nav']:.4f}  long {row['long_exposure']:.0%}  "
              f"short {row['short_exposure']:.0%}  trades {len(trades)}")
    with open(STATE, "w") as f:
        json.dump(state, f, indent=1)


if __name__ == "__main__":
    main()
