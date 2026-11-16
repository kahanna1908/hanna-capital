# Hanna Capital v3: Multi-Asset Trend Fund (design, fixed before testing)

Written and committed **before** the formula check was run, so the git history shows the rules
were not fitted to the results. Paper trading with simulated money only.

## Why a new fund instead of changing v2

v2 (the sector market-neutral fund) launched live on 2026-11-16 and stays untouched. Its
pre-launch check showed almost no edge: about −1.6%/yr before 2020 and +1.0%/yr after, net of fees.
The likely causes were structural, not parameter choices:

1. **Narrow universe.** 11 U.S. sectors are highly correlated, so the long/short spread is small.
2. **Equal-dollar sizing.** A volatile sector (XLE) and a quiet one (XLP) got the same dollars.
3. **Drawdown rule trap.** After a −12% drawdown risk was halved, and at half risk the fund
   rarely climbed back to −6%, so it stayed under-risked for long stretches (realized vol ~6% vs 10%).

v3 changes the structure, using well-documented defaults from published research rather than
values searched on this data.

## The formula

**Universe: 32 ETFs in 4 asset classes**, all listed before 2008:

| Class | ETFs |
|---|---|
| Equities (18) | SPY QQQ IWM MDY EFA EEM EWJ EWG EWU EWC EWA EWZ EWH EWY EWT FXI VNQ RWX |
| Bonds (6) | IEF TLT LQD TIP HYG EMB |
| Commodities (5) | GLD SLV DBC USO DBA |
| Currencies (3) | UUP FXE FXY |

**Signal (time-series momentum, Moskowitz, Ooi & Pedersen 2012).** For each ETF:

```
signal = average of sign(excess return) over 3, 6 and 12 months     → −1, −⅓, +⅓ or +1
excess return = ETF total return − T-bill return over the same window
```

A positive signal means long, negative means short. Averaging three lookbacks is the common
robust variant, not a tuned choice.

**Sizing (risk parity across classes).**
- Each asset class gets an equal share of risk (¼ each).
- Within a class, each ETF is sized by inverse volatility (63-day), so a bond ETF and an oil ETF
  carry similar risk.
- The whole book is then scaled to **10% expected annual volatility** with the 126-day covariance.
  Gross exposure is capped at 400%, and any one position at 50% of NAV.

**Trading.** Rebalance at the first close of each month. Skip trades under 0.2% of NAV.
Signals use the prior close; fills happen at today's close.

**No market hedge and no drawdown rule.** Trend following is not built to be market-neutral. It can
be net long or net short, and its beta to SPY is reported, not forced to zero. The volatility
target is the only risk control, which avoids v2's stuck-at-half-risk problem.

**Costs and fees.** 5 bp per trade (a bit above v2, since some ETFs trade with wider spreads),
1.0%/yr borrow on shorts, 1.5% management fee, 15% performance fee over a high-water mark. Cash
earns the T-bill rate; negative cash pays T-bill + 1%.

## Test plan (committed in advance)

1. Run `python -m v3.check --demo` (random prices) to test the code only.
2. Run `python -m v3.check` on real prices **once**, from 2008-12-31, split at 2020-01-01.
3. Fix only real bugs: crashes, wrong accounting, exposures outside the caps, or anything the
   rules above don't describe. **Do not change parameters to improve the result**, before or
   after 2020.
4. If it isn't broken, launch on a date set after the check, never backdated. If it is weak,
   it launches anyway and gets reported honestly next to v2.

## Expectations, stated up front

Published trend-following results across futures show Sharpe ratios around 0.5–1.0 before fees,
over many decades and far more markets than 32 ETFs. A realistic hope for v3 is a Sharpe of
0.3–0.7 net of fees, which at 10% volatility is about 3–7% a year above cash. That is not 1% a month,
and no honest design here is expected to reach that.
