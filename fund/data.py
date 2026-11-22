"""
Reliable daily closes from Yahoo Finance, shared by every fund version.

yfinance's parallel download can fail one ticker at random ("database is locked"), which left v2 unable
to book 2026-11-18 to 2026-11-20 until this fix. Here tickers download one at a time, and any ticker that
comes back empty is retried before giving up. This only changes how prices are fetched, never the formula.
"""

import time

import pandas as pd


def closes(tickers: list, start: str, attempts: int = 4) -> pd.DataFrame:
    import yfinance as yf

    def fetch(ts):
        raw = yf.download(ts, start=start, auto_adjust=True, progress=False, threads=False)["Close"]
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(ts[0])
        raw.index = pd.to_datetime(raw.index).tz_localize(None)
        return raw

    out = fetch(tickers)
    for n in range(1, attempts):
        missing = [t for t in tickers if t not in out or out[t].isna().all()]
        if not missing:
            break
        print(f"Retrying download for {', '.join(missing)} (attempt {n + 1} of {attempts})")
        time.sleep(3 * n)
        extra = fetch(missing)
        out = out.drop(columns=[t for t in missing if t in out]).join(extra[[t for t in missing if t in extra]], how="outer")
    return out.reindex(columns=tickers).sort_index()
