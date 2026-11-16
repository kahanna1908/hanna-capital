"""v3 settings, fixed before the formula check (see v3/DESIGN.md). Changing these after launch changes the track record."""

VERSION = "v3"
FUND_NAME = "Hanna Capital Multi-Asset Trend Fund"
MANAGER = "Kyle Hanna"
LAUNCH_DATE = "2026-11-17"        # first trading close v3 acts on, set after the formula check; never backdated
START_CAPITAL = 10_000_000
START_NAV = 100.0
DATA_DIR = "data/v3"

CLASSES = {
    "Equities": ["SPY", "QQQ", "IWM", "MDY", "EFA", "EEM", "EWJ", "EWG", "EWU", "EWC",
                 "EWA", "EWZ", "EWH", "EWY", "EWT", "FXI", "VNQ", "RWX"],
    "Bonds": ["IEF", "TLT", "LQD", "TIP", "HYG", "EMB"],
    "Commodities": ["GLD", "SLV", "DBC", "USO", "DBA"],
    "Currencies": ["UUP", "FXE", "FXY"],
}
ASSETS = [t for ts in CLASSES.values() for t in ts]
BENCHMARK = "SPY"
RATE_TICKER = "^IRX"              # 13-week Treasury bill yield
NAMES = {
    "SPY": "S&P 500", "QQQ": "Nasdaq-100", "IWM": "Russell 2000", "MDY": "S&P MidCap 400",
    "EFA": "Developed ex-US", "EEM": "Emerging markets", "EWJ": "Japan", "EWG": "Germany",
    "EWU": "United Kingdom", "EWC": "Canada", "EWA": "Australia", "EWZ": "Brazil",
    "EWH": "Hong Kong", "EWY": "South Korea", "EWT": "Taiwan", "FXI": "China large-cap",
    "VNQ": "U.S. REITs", "RWX": "International REITs",
    "IEF": "7-10y Treasuries", "TLT": "20+y Treasuries", "LQD": "Investment-grade corporates",
    "TIP": "TIPS", "HYG": "High-yield corporates", "EMB": "EM sovereign bonds",
    "GLD": "Gold", "SLV": "Silver", "DBC": "Broad commodities", "USO": "Crude oil",
    "DBA": "Agriculture", "UUP": "U.S. dollar", "FXE": "Euro", "FXY": "Japanese yen",
}

# signal: average sign of excess return over these lookbacks (trading days: 3, 6, 12 months)
LOOKBACKS = [63, 126, 252]

# risk
VOL_WINDOW = 63                   # per-asset volatility for inverse-vol sizing
COV_WINDOW = 126                  # portfolio covariance for the volatility target
VOL_TARGET = 0.10
MAX_GROSS = 4.0
MAX_POSITION = 0.50

# costs and fees
COST_BPS = 5
BORROW_FEE = 0.01
MGMT_FEE, PERF_FEE = 0.015, 0.15
MIN_TRADE = 0.002
