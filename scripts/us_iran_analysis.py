"""US-Iran Analysis — Sequential fetch to avoid rate limits."""
import sys, time, json
sys.path.insert(0, "d:/Github/Agent/digital-oracle")
from digital_oracle import (
    USTreasuryProvider, YieldCurveQuery,
    YahooPriceProvider, PriceHistoryQuery,
    FearGreedProvider,
    PolymarketProvider, PolymarketEventQuery,
    WebSearchProvider, WebSearchQuery,
)

def safe_fetch(name, fn, delay=2):
    for attempt in range(3):
        try:
            result = fn()
            print(f"  ✓ {name}")
            return result
        except Exception as e:
            err = str(e)[:120]
            if "429" in err or "Rate limited" in err or "Too Many Requests" in err:
                print(f"  ⏳ {name} rate-limited, waiting 10s...")
                time.sleep(10)
            elif attempt < 2:
                print(f"  ⚠ {name} retry {attempt+1}: {err}")
                time.sleep(delay * (attempt + 1))
            else:
                print(f"  ✗ {name} FAILED: {err}")
    return None

def analyze_price(history):
    """Extract closes and compute changes from PriceHistory."""
    if history is None or len(history.bars) == 0:
        return None
    closes = [b.close for b in history.bars]
    latest = closes[-1]
    result = {"latest": latest, "n_bars": len(closes)}
    if len(closes) >= 6:
        result["7d"] = (closes[-1]/closes[-6] - 1)*100
    if len(closes) >= 11:
        result["14d"] = (closes[-1]/closes[-11] - 1)*100
    if len(closes) >= 21:
        result["30d"] = (closes[-1]/closes[-21] - 1)*100
    if len(closes) >= 42:
        result["60d"] = (closes[-1]/closes[-42] - 1)*100
    return result

yahoo = YahooPriceProvider()
treasury = USTreasuryProvider()
fear = FearGreedProvider()
poly = PolymarketProvider()
web = WebSearchProvider()

print("=" * 70)
print("US-IRAN ANALYSIS — MARKET DATA COLLECTION")
print("=" * 70)

# ── Treasury & Sentiment ──
print("\n── [1] Treasury & Sentiment ──")
time.sleep(1)
nominal = treasury.latest_yield_curve(YieldCurveQuery())
n_1m, n_3m = nominal.yield_for('1M'), nominal.yield_for('3M')
n_2y, n_10y, n_30y = nominal.yield_for('2Y'), nominal.yield_for('10Y'), nominal.yield_for('30Y')
print(f"  Nominal: 1M={n_1m:.2f}% 3M={n_3m:.2f}% 2Y={n_2y:.2f}% 10Y={n_10y:.2f}% 30Y={n_30y:.2f}%")
print(f"  Spreads: 3M→10Y={n_10y-n_3m:+.2f}% 2Y→10Y={n_10y-n_2y:+.2f}%")

time.sleep(0.5)
real = treasury.latest_yield_curve(YieldCurveQuery(curve_kind="real"))
be_10y = be_30y = None
if real:
    r_10y = real.yield_for('10Y'); r_30y = real.yield_for('30Y')
    be_10y = n_10y - r_10y; be_30y = n_30y - r_30y
    print(f"  TIPS: 10Y={r_10y:.2f}% 30Y={r_30y:.2f}%")
    print(f"  BE Inflation: 10Y={be_10y:.2f}% 30Y={be_30y:.2f}%")

time.sleep(0.5)
fg = fear.get_index()
print(f"  Fear&Greed: {fg.score:.1f} ({fg.rating}) | 1W ago: {fg.one_week_ago:.1f} | 1M ago: {fg.one_month_ago:.1f}")

# ── Key Assets ──
print("\n── [2] Key Asset Prices (serial) ──")
assets = [
    ("Gold (GC=F)", "GC=F"),
    ("WTI Oil (CL=F)", "CL=F"),
    ("Brent Oil (BZ=F)", "BZ=F"),
    ("DXY", "DX-Y.NYB"),
    ("VIX", "^VIX"),
    ("S&P500 (SPY)", "SPY"),
]

prices = {}
for name, sym in assets:
    time.sleep(4)
    r = safe_fetch(name, lambda s=sym: yahoo.get_history(PriceHistoryQuery(symbol=s, limit=60)))
    data = analyze_price(r)
    if data:
        latest = data["latest"]
        fmt = f"${latest:,.2f}" if latest > 1 else f"{latest:.4f}"
        changes = []
        for period in ["7d", "14d", "30d", "60d"]:
            if period in data:
                changes.append(f"{period}: {data[period]:+.2f}%")
        print(f"    {fmt} | {' | '.join(changes)}")
        prices[name] = data
    else:
        print(f"    NO DATA")
        prices[name] = None

# ── Defense Sector ──
print("\n── [3] Defense Sector ──")
defense_names = [
    ("Lockheed Martin", "LMT"),
    ("Northrop Grumman", "NOC"),
    ("RTX (Raytheon)", "RTX"),
    ("General Dynamics", "GD"),
    ("ITA (Aerospace&Defense ETF)", "ITA"),
    ("PPA (Aerospace&Defense ETF)", "PPA"),
]

defense = {}
for name, sym in defense_names:
    time.sleep(3)
    r = safe_fetch(name, lambda s=sym: yahoo.get_history(PriceHistoryQuery(symbol=s, limit=60)))
    data = analyze_price(r)
    if data:
        latest = data["latest"]
        fmt = f"${latest:,.2f}"
        changes = []
        for period in ["7d", "14d", "30d", "60d"]:
            if period in data:
                changes.append(f"{period}: {data[period]:+.2f}%")
        print(f"    {fmt} | {' | '.join(changes)}")
        defense[name] = data
    else:
        print(f"    NO DATA")
        defense[name] = None

# ── Polymarket ──
print("\n── [4] Polymarket Event Markets ──")
keywords = ["iran", "middle-east", "israel", "oil", "sanctions", "war", "geopolitical"]
seen_titles = set()
all_poly_events = []
for q in keywords:
    time.sleep(1.5)
    try:
        events = poly.list_events(PolymarketEventQuery(slug_contains=q, limit=20, active=True))
        if events:
            for evt in events:
                title = evt.title or ""
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                title_lower = title.lower()
                relevant_kw = any(kw in title_lower for kw in
                    ["iran", "israel", "middle", "oil", "sanction", "war", "persian",
                     "strait", "hormuz", "nuclear", "bomb", "missile", "navy", "naval"])
                if relevant_kw:
                    vol = f"${evt.volume_usd:,.0f}" if evt.volume_usd else "N/A"
                    print(f"  {title[:130]}")
                    print(f"    Vol: {vol}")
                    all_poly_events.append({"title": title, "volume": evt.volume_usd})
        else:
            print(f"  [{q}] 0 results")
    except Exception as e:
        err_msg = str(e)[:100]
        print(f"  [{q}] Skip: {err_msg}")

# ── Web Search ──
print("\n── [5] Web Search Supplemental ──")
time.sleep(1)
try:
    sr = web.search(WebSearchQuery(query="oil tanker insurance rates Persian Gulf Strait of Hormuz 2026"))
    print(f"  ✓ Oil shipping risk: {len(str(sr))} chars")
except Exception as e:
    print(f"  ✗: {str(e)[:100]}")

time.sleep(2)
try:
    sr2 = web.search(WebSearchQuery(query="US Iran nuclear negotiations IAEA June 2026"))
    print(f"  ✓ US-Iran nuke talks: {len(str(sr2))} chars")
except Exception as e:
    print(f"  ✗: {str(e)[:100]}")

# ── Summary ──
print("\n" + "=" * 70)
print("DATA SNAPSHOT")
print("=" * 70)
summary = {
    "date": "2026-06-01",
    "treasury": {"1M": n_1m, "3M": n_3m, "2Y": n_2y, "10Y": n_10y, "30Y": n_30y,
                 "spread_3m10y": round(n_10y-n_3m, 2), "spread_2y10y": round(n_10y-n_2y, 2),
                 "be_10y": round(be_10y, 2) if be_10y else None},
    "fear_greed": {"score": round(fg.score, 1), "rating": fg.rating,
                   "1w_ago": round(fg.one_week_ago, 1), "1m_ago": round(fg.one_month_ago, 1)},
    "prices": {k: {"latest": round(v["latest"], 2), "7d": round(v.get("7d", 0), 2) if v.get("7d") else None,
                   "30d": round(v.get("30d", 0), 2) if v.get("30d") else None,
                   "60d": round(v.get("60d", 0), 2) if v.get("60d") else None}
              for k, v in prices.items() if v},
    "defense": {k: {"latest": round(v["latest"], 2), "7d": round(v.get("7d", 0), 2) if v.get("7d") else None,
                    "30d": round(v.get("30d", 0), 2) if v.get("30d") else None,
                    "60d": round(v.get("60d", 0), 2) if v.get("60d") else None}
              for k, v in defense.items() if v},
    "polymarket_relevant_events": len(all_poly_events),
}
print(json.dumps(summary, indent=2, default=str))
print("=" * 70)
print("COLLECTION COMPLETE")
