"""DO Analysis: A-share short-to-medium term outlook — multi-signal fetch."""
import sys
sys.path.insert(0, "d:/Github/Agent/digital-oracle")
from digital_oracle import (
    USTreasuryProvider, YieldCurveQuery,
    YahooPriceProvider, PriceHistoryQuery,
    FearGreedProvider,
    BisProvider, BisCreditGapQuery,
    gather,
)

treasury = USTreasuryProvider()
yahoo = YahooPriceProvider()
fear = FearGreedProvider()
bis = BisProvider()

print("=== Fetching A-share / China signals ===\n")

result = gather({
    # Layer 1: Direct China ETF pricing
    "fxi": lambda: yahoo.get_history(PriceHistoryQuery(symbol="FXI", limit=90)),
    "ashr": lambda: yahoo.get_history(PriceHistoryQuery(symbol="ASHR", limit=90)),
    "kweb": lambda: yahoo.get_history(PriceHistoryQuery(symbol="KWEB", limit=90)),
    "mchi": lambda: yahoo.get_history(PriceHistoryQuery(symbol="MCHI", limit=90)),

    # Layer 2: China consumer / tech (US-listed proxies)
    "baba": lambda: yahoo.get_history(PriceHistoryQuery(symbol="BABA", limit=30)),
    "jd": lambda: yahoo.get_history(PriceHistoryQuery(symbol="JD", limit=30)),
    "byddy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="BYDDY", limit=30)),

    # Layer 3: Commodities — copper = China industrial demand proxy
    "copper": lambda: yahoo.get_history(PriceHistoryQuery(symbol="HG=F", limit=30)),
    "gold": lambda: yahoo.get_history(PriceHistoryQuery(symbol="GC=F", limit=30)),

    # Layer 4: FX — yuan and DXY
    "cny": lambda: yahoo.get_history(PriceHistoryQuery(symbol="CNY=X", limit=30)),
    "dxy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="DX-Y.NYB", limit=30)),
    "eurusd": lambda: yahoo.get_history(PriceHistoryQuery(symbol="EURUSD=X", limit=30)),

    # Layer 5: Global risk context
    "spy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="SPY", limit=30)),
    "vix": lambda: yahoo.get_history(PriceHistoryQuery(symbol="^VIX", limit=30)),

    # Layer 6: Yield curves & credit
    "nominal": lambda: treasury.latest_yield_curve(YieldCurveQuery()),
    "real": lambda: treasury.latest_yield_curve(YieldCurveQuery(curve_kind="real")),
    "bis_credit": lambda: bis.get_credit_to_gdp(BisCreditGapQuery()),

    # Layer 7: Sentiment
    "fear_greed": lambda: fear.get_index(),
}, timeout_seconds=120)

for k, v in result.results.items():
    print(f"=== {k} ===")
    print(v)
    print()

if result.errors:
    print("=== ERRORS ===")
    for k, e in result.errors.items():
        print(f"  {k}: {e}")
