"""
Build the website from each fund's books:
  site/index.html     v2, the sector market-neutral fund (books in data/)
  site/v3/index.html  v3, the multi-asset trend fund (books in data/v3/)

    python site/build.py
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from fund import config as V2  # noqa: E402
from v3 import config as V3  # noqa: E402


def read_csv(data_dir, name):
    path = os.path.join(ROOT, data_dir, name)
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def read_json(data_dir, name):
    path = os.path.join(ROOT, data_dir, name)
    return json.load(open(path)) if os.path.exists(path) else None


def build(C, data_dir, out_rel, page):
    nav = [{k: (v if k == "date" else float(v)) for k, v in r.items()} for r in read_csv(data_dir, "nav.csv")]
    trades = read_csv(data_dir, "trades.csv")
    state = read_json(data_dir, "state.json")
    check = read_json(data_dir, "check.json")

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
            "spyAtLaunch": spy_at_launch, "repo": f"https://github.com/{repo}", **page}
    tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    out = os.path.join(HERE, out_rel)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(tpl.replace("__FUND_DATA__", json.dumps(data, separators=(",", ":")), 1))
    print(f"Wrote {out} ({len(nav)} days, {len(trades)} trades)")


def v3_page():
    C = V3
    classes = " · ".join(f"{k} ({len(v)})" for k, v in C.CLASSES.items())
    months = " / ".join(str(n // 21) for n in C.LOOKBACKS)
    return {
        "about": (f"A multi-asset trend-following fund across {len(C.ASSETS)} ETFs in four asset classes: stocks, bonds, "
                  "commodities and currencies. Each month it goes long what has been rising and short what has been falling, "
                  "with every asset class given an equal share of risk. Launched as v3 after the v2 sector fund's pre-launch "
                  "check showed little edge; v2 keeps running and is reported alongside it. A script runs after every market "
                  "close, makes the trades, and updates this page."),
        "formulaHtml": (f'<span class="k">signal</span> = average of sign(<span class="k">excess return</span>) over {months} months<br>'
                        '<span class="c">excess return = ETF total return − T-bill return over the same window<br>'
                        'signal is −1, −⅓, +⅓ or +1: positive means long, negative means short</span>'),
        "rules": [
            f"<b>Universe:</b> {classes}.",
            f"<b>Size</b> each asset class to an equal share of risk, and each ETF within a class by inverse "
            f"{C.VOL_WINDOW}-day volatility, so a bond ETF and an oil ETF carry similar risk.",
            f"<b>Scale</b> the whole book to {C.VOL_TARGET * 100:.0f}% expected annual volatility, capped at "
            f"{C.MAX_GROSS * 100:.0f}% gross exposure and {C.MAX_POSITION * 100:.0f}% of the fund in any one ETF.",
            "<b>Rebalance</b> at the first close of each month, skipping trades under "
            f"{C.MIN_TRADE * 100:.1f}% of the fund.",
            "<b>No market hedge, no drawdown rule.</b> Trend following can be net long or net short; its beta to SPY "
            "is reported, not forced to zero. The volatility target is the only risk control.",
        ],
        "betaNote": "not hedged",
        "otherFund": {"label": "← v2 fund", "href": "../"},
    }


def main():
    build(V2, "data", "index.html", {"otherFund": {"label": "v3 fund →", "href": "v3/"}})
    build(V3, V3.DATA_DIR, os.path.join("v3", "index.html"), v3_page())


if __name__ == "__main__":
    main()
