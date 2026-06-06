"""DO Analysis: AI server industry outlook — multi-signal fetch."""
import sys
sys.path.insert(0, "d:/Github/Agent/digital-oracle")
from digital_oracle import (
    USTreasuryProvider, YieldCurveQuery,
    YahooPriceProvider, PriceHistoryQuery,
    FearGreedProvider,
    BisProvider, BisRateQuery, BisCreditGapQuery,
    YFinanceProvider, OptionsChainQuery,
    CftcCotProvider, CftcCotQuery,
    gather,
)

treasury = USTreasuryProvider()
yahoo = YahooPriceProvider()
fear = FearGreedProvider()
bis = BisProvider()
yf = YFinanceProvider()
cftc = CftcCotProvider()

print("=== Fetching AI server industry signals ===\n")

result = gather({
    # Layer 1: Direct AI server / GPU exposure
    "nvda": lambda: yahoo.get_history(PriceHistoryQuery(symbol="NVDA", limit=120)),
    "smci": lambda: yahoo.get_history(PriceHistoryQuery(symbol="SMCI", limit=120)),
    "dell": lambda: yahoo.get_history(PriceHistoryQuery(symbol="DELL", limit=120)),
    "amd": lambda: yahoo.get_history(PriceHistoryQuery(symbol="AMD", limit=120)),

    # Layer 2: Semiconductor indices
    "smh": lambda: yahoo.get_history(PriceHistoryQuery(symbol="SMH", limit=90)),
    "sox": lambda: yahoo.get_history(PriceHistoryQuery(symbol="^SOX", limit=90)),

    # Layer 3: Cloud capex proxies
    "avgo": lambda: yahoo.get_history(PriceHistoryQuery(symbol="AVGO", limit=90)),
    "mu": lambda: yahoo.get_history(PriceHistoryQuery(symbol="MU", limit=90)),
    "intc": lambda: yahoo.get_history(PriceHistoryQuery(symbol="INTC", limit=90)),

    # Layer 4: Macro / liquidity context
    "spy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="SPY", limit=90)),
    "vix": lambda: yahoo.get_history(PriceHistoryQuery(symbol="^VIX", limit=90)),
    "dxy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="DX-Y.NYB", limit=90)),
    "copper": lambda: yahoo.get_history(PriceHistoryQuery(symbol="HG=F", limit=90)),

    # Layer 5: Yield curve & credit
    "nominal_curve": lambda: treasury.latest_yield_curve(YieldCurveQuery()),
    "real_curve": lambda: treasury.latest_yield_curve(YieldCurveQuery(curve_kind="real")),
    "bis_credit_gap": lambda: bis.get_credit_to_gdp(BisCreditGapQuery()),

    # Layer 6: Sentiment / positioning
    "fear_greed": lambda: fear.get_index(),
    "cftc_sp500": lambda: cftc.list_reports(CftcCotQuery(commodity_name="S&P 500", limit=2)),

    # Layer 7: NVDA options for forward vol
    "nvda_options": lambda: yf.get_chain(OptionsChainQuery(ticker="NVDA")),

}, timeout_seconds=120)

for k, v in result.results.items():
    print(f"=== {k} ===")
    print(v)
    print()

if result.errors:
    print("=== ERRORS ===")
    for k, e in result.errors.items():
        print(f"  {k}: {e}")
