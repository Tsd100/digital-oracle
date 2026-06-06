"""DO Analysis: Oil short-to-medium term from liquidity perspective."""
import sys
sys.path.insert(0, "d:/Github/Agent/digital-oracle")
from digital_oracle import (
    USTreasuryProvider, YieldCurveQuery,
    YahooPriceProvider, PriceHistoryQuery,
    FearGreedProvider, CMEFedWatchProvider,
    CftcCotProvider, CftcCotQuery,
    BisProvider, BisRateQuery, BisCreditGapQuery,
    YFinanceProvider, OptionsChainQuery,
    gather,
)

treasury = USTreasuryProvider()
yahoo = YahooPriceProvider()
fear = FearGreedProvider()
cme = CMEFedWatchProvider()
cftc = CftcCotProvider()
bis = BisProvider()
yf = YFinanceProvider()

print("=== Fetching all signals in parallel ===\n")

result = gather({
    # Layer 1: Direct oil pricing
    "oil_wti": lambda: yahoo.get_history(PriceHistoryQuery(symbol="CL=F", limit=120)),
    "oil_brent": lambda: yahoo.get_history(PriceHistoryQuery(symbol="BZ=F", limit=120)),

    # Layer 2: Dollar & real rates (liquidity core)
    "dxy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="DX-Y.NYB", limit=90)),
    "nominal_curve": lambda: treasury.latest_yield_curve(YieldCurveQuery()),
    "real_curve": lambda: treasury.latest_yield_curve(YieldCurveQuery(curve_kind="real")),

    # Layer 3: Risk appetite & stress
    "vix": lambda: yahoo.get_history(PriceHistoryQuery(symbol="^VIX", limit=90)),
    "fear_greed": lambda: fear.get_index(),
    "spy": lambda: yahoo.get_history(PriceHistoryQuery(symbol="SPY", limit=90)),

    # Layer 4: Competing commodities
    "gold": lambda: yahoo.get_history(PriceHistoryQuery(symbol="GC=F", limit=90)),
    "copper": lambda: yahoo.get_history(PriceHistoryQuery(symbol="HG=F", limit=90)),

    # Layer 5: Institutional positioning
    "cftc_oil": lambda: cftc.get_current(CftcCotQuery(market="crude_oil")),

    # Layer 6: Fed rate expectations
    "fedwatch": lambda: cme.get_current(),

    # Layer 7: Global credit conditions
    "bis_rates": lambda: bis.latest_policy_rates(BisRateQuery()),
    "bis_credit_gap": lambda: bis.latest_credit_gap(BisCreditGapQuery()),

    # Layer 8: USO options for forward-looking oil vol
    "uso_options": lambda: yf.get_options_chain(OptionsChainQuery(symbol="USO")),
}, timeout_seconds=120)

for k, v in result.results.items():
    print(f"=== {k} ===")
    print(v)
    print()

if result.errors:
    print("=== ERRORS ===")
    for k, e in result.errors.items():
        print(f"  {k}: {e}")
