"""Every setting the fund uses, in one place. Changing these after launch changes the track record."""

FUND_NAME = "Hanna Capital Market-Neutral Fund"
MANAGER = "Kyle Hanna"
LAUNCH_DATE = "2026-11-16"        # first trading close the fund acts on; nothing earlier is ever traded
START_CAPITAL = 10_000_000
START_NAV = 100.0

# universe: the 11 Select Sector SPDR ETFs, hedged with SPY
SECTORS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]
HEDGE = "SPY"
RATE_TICKER = "^IRX"              # 13-week Treasury bill yield, used for interest on cash
NAMES = {"XLK": "Technology", "XLF": "Financials", "XLE": "Energy", "XLV": "Health Care",
         "XLI": "Industrials", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
         "XLU": "Utilities", "XLB": "Materials", "XLRE": "Real Estate", "XLC": "Communication Services",
         "SPY": "S&P 500 (hedge)"}

# the formula: score = W_MOM * z(momentum) + W_TREND * z(trend)
W_MOM, W_TREND = 0.6, 0.4
MOM_LOOKBACK, MOM_SKIP, TREND_SMA = 252, 21, 200
N_SIDE = 3                        # names held long and short
EXIT_RANK = 5                     # buffer: a holding is kept until it falls below this rank

# risk
VOL_TARGET = 0.10
COV_WINDOW, BETA_WINDOW = 126, 252
MAX_GROSS = 3.0                   # long + short exposure cap, as a multiple of NAV
MAX_POSITION = 0.60
DD_CUT, DD_RESET = -0.12, -0.06   # halve risk below -12% from peak, restore above -6%

# costs and fees
COST_BPS = 4                      # commission + slippage per dollar traded
BORROW_FEE = 0.005                # annual, on short market value
MGMT_FEE, PERF_FEE = 0.015, 0.15  # 1.5% management, 15% performance above a high-water mark
MIN_TRADE = 0.002                 # skip trades under 0.2% of NAV
