# Hanna Capital Market-Neutral Fund

A **live paper-traded** long/short hedge fund that I built and run with code. It launched with **$10,000,000** of simulated capital at the market close on **November 16, 2026**, and it updates itself after every close.

**Live track record:** https://kahanna1908.github.io/hanna-capital/

Every day's NAV, position and trade is committed to this repository right after the close, so the git history is a time-stamped audit trail. Results can't be backfilled or edited after the fact.

## Strategy

The fund ranks the 11 U.S. sector ETFs (XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC) on one score:

```
score = 0.6 × z(momentum) + 0.4 × z(trend)

momentum = 12-month return, skipping the most recent month
trend    = price relative to its 200-day moving average
z(x)     = standard deviations above the average sector that day
```

| Step | Rule |
|---|---|
| Rebalance | First close of each month |
| Long / short | Top 3 long, bottom 3 short, equal dollars per name |
| Turnover buffer | A holding is kept until it falls below rank 5 |
| Sizing | Scaled to 10% expected annual volatility, gross exposure capped at 300% |
| Market hedge | Book beta (252-day) offset with SPY, targeting beta ≈ 0 |
| Drawdown control | Risk halved below −12% from peak, restored above −6% |

## Fund terms (simulated)

- 1.5% management fee (accrued daily) and 15% performance fee above a high-water mark (crystallized annually)
- 4 bp per trade for commission and slippage, 0.5%/yr short borrow fee
- Cash earns the 13-week Treasury bill rate (`^IRX`)
- Fills at the daily closing price; signals use only the prior close, so there's no look-ahead

## How it runs

| File | What it does |
|---|---|
| `fund/config.py` | Every parameter, fixed before launch |
| `fund/engine.py` | The formula, position sizing, beta hedge, fees and accounting |
| `fund/run_daily.py` | Downloads the latest closes and processes each new trading day |
| `fund/check.py` | One pre-launch run of the same engine over 2009–2026, as a sanity check |
| `site/` | Builds the live website from `data/` |
| `.github/workflows/daily.yml` | Runs after every weekday close, commits the books, publishes the site |

The fund's books live in `data/`: `nav.csv` (daily NAV and exposures), `trades.csv` (every fill), and `state.json` (positions, cash, high-water mark).

## Disclaimer

Paper trading with simulated money. No real capital is invested and no outside money is accepted. This is not investment advice.

*Built by Kyle Hanna, Fordham University Gabelli School of Business.*
