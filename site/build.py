"""
Build site/index.html from the fund's books in data/.

    python site/build.py
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from fund import config as C  # noqa: E402


def read_csv(name):
    path = os.path.join(ROOT, "data", name)
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    nav = [{k: (v if k == "date" else float(v)) for k, v in r.items()} for r in read_csv("nav.csv")]
    trades = read_csv("trades.csv")
    state_path = os.path.join(ROOT, "data", "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else None
    check_path = os.path.join(ROOT, "data", "check.json")
    check = json.load(open(check_path)) if os.path.exists(check_path) else None

    positions, cash, totals = [], C.START_CAPITAL, {}
    if state:
        cash, totals = state["cash"], state["totals"]
        equity = nav[-1]["equity"] if nav else C.START_CAPITAL
        for t, q in state["shares"].items():
            p = state["last_prices"].get(t)
            if p is None:
                continue
            avg = state["avg_cost"].get(t, p)
            positions.append({"symbol": t, "name": C.NAMES.get(t, t), "shares": round(q, 2), "avg": avg,
                              "price": p, "value": q * p, "weight": q * p / equity, "pnl": (p - avg) * q})
        positions.sort(key=lambda x: -x["weight"])
    else:
        totals = {"Management fees": 0, "Performance fees": 0, "Trading costs": 0, "Borrow costs": 0, "Interest earned": 0}

    # the fund takes its first positions at the launch close, so SPY is measured from that same close
    spy_at_launch = nav[0]["spy"] if nav else None

    cfg = {k: getattr(C, k) for k in dir(C) if k.isupper()}
    repo = os.environ.get("GITHUB_REPOSITORY", "kahanna1908/hanna-capital")
    data = {"config": cfg, "nav": nav, "positions": positions, "cash": cash, "totals": totals,
            "trades": trades[::-1][:30], "nTrades": len(trades), "check": check,
            "spyAtLaunch": spy_at_launch, "repo": f"https://github.com/{repo}"}
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    out = os.path.join(HERE, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl.replace("__FUND_DATA__", json.dumps(data, separators=(",", ":")), 1))
    print(f"Wrote {out} ({len(nav)} days, {len(trades)} trades)")


if __name__ == "__main__":
    main()
