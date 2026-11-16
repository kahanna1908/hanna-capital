"""
Code test on simulated prices: run both funds' engines for ~18 months of fake data, write their trade
journals, and print a sample. Used only by the "Code test" workflow; nothing it writes is committed.

    python -m tools.demo_journal
"""

import json
import os

from fund import check as c2, engine as e2, journal as j2
from v3 import check as c3, config as C3, engine as e3, journal as j3


def run_v2():
    px, rate = c2.simulated()
    sc, rets = e2.scores(px), px.pct_change()
    st, out = e2.new_state(), []
    for i in range(px.index.get_loc(px.index[px.index >= "2025-06-02"][0]), len(px)):
        row, trades = e2.step(st, px.index[i], px.iloc[i], sc.iloc[i - 1], rets.iloc[1:i], float(rate.iloc[i]))
        e = j2.entry(px.index[i], px, i, sc, trades, st, row)
        if e:
            out.append(e)
    return out


def run_v3():
    px, rate = c3.simulated()
    px = px.ffill(limit=5)
    sig, rets = e3.signals(px, rate), px.pct_change(fill_method=None)
    st, out = e3.new_state(), []
    for i in range(px.index.get_loc(px.index[px.index >= "2025-06-02"][0]), len(px)):
        row, trades = e3.step(st, px.index[i], px.iloc[i], sig.iloc[i - 1], rets.iloc[1:i], float(rate.iloc[i]))
        e = j3.entry(px.index[i], px, i, sig, rate, rets, trades, st, row)
        if e:
            out.append(e)
    return out


def main():
    lines = ["## Trade journal code test (SIMULATED PRICES)"]
    for name, entries, path in [("v2", run_v2(), "data/journal.jsonl"),
                                ("v3", run_v3(), os.path.join(C3.DATA_DIR, "journal.jsonl"))]:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.writelines(json.dumps(e) + "\n" for e in entries)
        assert entries, f"{name}: no journal entries"
        kinds = sorted({t["action"] for e in entries for t in e["trades"]})
        last = entries[-1]
        lines += ["", f"### {name}: {len(entries)} rebalances, actions seen: {', '.join(kinds)}",
                  "", f"**{last['date']}**: {last['summary']}", ""]
        lines += [f"- {t['action']} {t['ticker']}: {t['why']}" for t in last["trades"][:6]]
    text = "\n".join(lines)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
