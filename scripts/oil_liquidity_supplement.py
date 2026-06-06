"""Supplementary data fetch for oil liquidity analysis."""
import sys
sys.path.insert(0, "d:/Github/Agent/digital-oracle")
from digital_oracle import (
    CftcCotProvider, CftcCotQuery,
    CMEFedWatchProvider,
    BisProvider, BisRateQuery, BisCreditGapQuery,
    YFinanceProvider, OptionsChainQuery,
    gather,
)

cftc = CftcCotProvider()
cme = CMEFedWatchProvider()
bis = BisProvider()
yf = YFinanceProvider()

result = gather({
    "cftc_oil": lambda: cftc.list_reports(CftcCotQuery(commodity_name="CRUDE OIL", limit=3)),
    "fedwatch": lambda: cme.get_probabilities(),
    "bis_rates": lambda: bis.get_policy_rates(BisRateQuery()),
    "bis_credit_gap": lambda: bis.get_credit_to_gdp(BisCreditGapQuery()),
    "uso_chain": lambda: yf.get_chain(OptionsChainQuery(symbol="USO")),
}, timeout_seconds=90)

for k, v in result.results.items():
    print(f"=== {k} ===")
    print(v)
    print()

if result.errors:
    print("=== ERRORS ===")
    for k, e in result.errors.items():
        print(f"  {k}: {e}")
