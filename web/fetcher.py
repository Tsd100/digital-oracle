"""Data fetcher — select providers based on question keywords, call via gather()."""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from queue import Queue
from typing import Any, Callable

# Ensure project root on path for digital_oracle imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from digital_oracle import (
    BisProvider, BisRateQuery, BisCreditGapQuery,
    CftcCotProvider, CftcCotQuery,
    CMEFedWatchProvider,
    CoinGeckoProvider, CoinGeckoPriceQuery,
    DeribitProvider, DeribitFuturesCurveQuery,
    EdgarProvider, EdgarInsiderQuery,
    FearGreedProvider,
    KalshiProvider, KalshiMarketQuery,
    PolymarketProvider, PolymarketEventQuery,
    USTreasuryProvider, YieldCurveQuery,
    WebSearchProvider, WebSearchQuery,
    WorldBankProvider, WorldBankQuery,
    YahooPriceProvider, PriceHistoryQuery,
    YFinanceProvider, OptionsChainQuery,
    gather,
)

# ---------------------------------------------------------------------------
# Keyword → provider mapping
# ---------------------------------------------------------------------------
PROVIDER_PATTERNS: dict[str, list[str]] = {
    # ---- Economy / Recession / Fed / Rates (English + Chinese) ----
    "recession|economy|gdp|inflation|fed|interest rate|yield|treasury|"
    "经济|衰退|通胀|美联储|加息|降息|利率|国债|收益率|"
    "宏观|景气|就业|非农|cpi|ppi|pce|gdp": [
        "treasury", "tips_real_yield", "fear_greed", "spy_price",
        "gold_price", "copper_price", "dxy", "cftc_gold",
        "cme_fedwatch", "kalshi_fed", "bis_rates", "bis_credit_gap",
        "polymarket_recession", "vix_direct", "web_hy",
    ],
    # ---- Geopolitical Conflict / War ----
    "war|conflict|geopolitic|military|invasion|taiwan|ukraine|"
    "战争|冲突|地缘|军事|入侵|台湾|乌克兰|中东|伊朗|朝鲜": [
        "polymarket_war", "gold_price", "oil_price", "fear_greed",
        "dxy", "eurusd", "cftc_gold", "cftc_oil", "treasury",
        "tips_real_yield", "vix_direct", "web_cds", "web_search",
    ],
    # ---- Stocks / Options / Crash / Bubble ----
    "stock|options|crash|bubble|nvda|aapl|spy|nasdaq|equity|"
    "股票|期权|崩盘|泡沫|英伟达|苹果|标普|纳指|道指|暴跌|回调": [
        "spy_price", "fear_greed", "treasury", "tips_real_yield",
        "vix_direct", "dxy", "cftc_sp500", "bis_credit_gap",
        "polymarket_recession", "web_vix", "yf_options",
    ],
    # ---- Crypto ----
    "crypto|bitcoin|btc|ethereum|eth|solana|"
    "加密货币|比特币|以太坊|索拉纳|山寨币|数字货币|web3|defi": [
        "coingecko", "deribit", "fear_greed", "vix_direct",
        "dxy", "gold_price", "web_search",
    ],
    # ---- Commodities / Gold / Oil / Copper ----
    "gold|commodity|oil|copper|silver|"
    "黄金|大宗商品|石油|原油|铜|白银|天然气|农产品": [
        "gold_price", "copper_price", "oil_price", "dxy",
        "cftc_gold", "cftc_copper", "cftc_oil",
        "treasury", "tips_real_yield", "fear_greed",
    ],
    # ---- China-specific ----
    "china|chinese|房价|房地产|a股|人民币|中国|沪深|中概|港股": [
        "gold_price", "copper_price", "treasury", "tips_real_yield",
        "dxy", "eurusd", "fear_greed", "spy_price",
        "bis_rates", "web_search",
    ],
    # ---- AI / Tech ----
    "ai|artificial intelligence|openai|anthropic|"
    "人工智能|大模型|算力|芯片|半导体|llm|gpu": [
        "spy_price", "fear_greed", "treasury", "polymarket_ai",
        "vix_direct", "bis_credit_gap", "web_search", "yf_options",
    ],
}

DEFAULT_PROVIDERS = [
    "spy_price", "fear_greed", "treasury", "tips_real_yield",
    "gold_price", "dxy", "vix_direct", "bis_rates",
    "web_search", "coingecko", "polymarket_recession",
]


def select_provider_labels(question: str) -> list[str]:
    lower = question.lower()
    for pattern_str, labels in PROVIDER_PATTERNS.items():
        patterns = pattern_str.split("|")
        if any(p in lower for p in patterns):
            return labels
    return DEFAULT_PROVIDERS


# ---------------------------------------------------------------------------
# Build callables for gather()
# ---------------------------------------------------------------------------

def _serialize(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        d = {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
        return _serialize(d)
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)


def build_tasks(labels: list[str]) -> dict[str, Callable[[], Any]]:
    tasks: dict[str, Callable[[], Any]] = {}
    import threading
    import time as _time
    import random as _random

    # Thread lock to serialize Yahoo Finance calls (avoid rate limiting)
    _yahoo_lock = threading.Lock()

    # These are constructed eagerly so they can be reused across lambdas
    yahoo = YahooPriceProvider()
    treasury = USTreasuryProvider()
    cftc = CftcCotProvider()
    coingecko = CoinGeckoProvider()
    pm = PolymarketProvider()
    deribit = DeribitProvider()
    fear = FearGreedProvider()
    web = WebSearchProvider()
    bis = BisProvider()
    # KalshiProvider, CMEFedWatchProvider — may need proxy; constructed lazily

    _label_to_yahoo = {
        "spy_price": "SPY", "gold_price": "GC=F", "copper_price": "HG=F",
        "oil_price": "CL=F", "vix_direct": "^VIX", "dxy": "DX-Y.NYB",
        "eurusd": "EURUSD=X",
    }

    for label in labels:
        if label == "treasury":
            tasks[label] = lambda t=treasury: t.latest_yield_curve(YieldCurveQuery())
        elif label == "fear_greed":
            tasks[label] = lambda f=fear: f.get_index()
        elif label in _label_to_yahoo:
            symbol = _label_to_yahoo[label]
            def _yahoo_task(sym=symbol, lock=_yahoo_lock):
                with lock:
                    _time.sleep(0.5 + _random.uniform(0, 0.5))
                return yahoo.get_history(PriceHistoryQuery(symbol=sym, limit=60))
            tasks[label] = _yahoo_task
        elif label == "cftc_gold":
            tasks[label] = lambda c=cftc: c.list_reports(CftcCotQuery(commodity_name="GOLD", limit=2))
        elif label == "cftc_sp500":
            tasks[label] = lambda c=cftc: c.list_reports(CftcCotQuery(commodity_name="S&P 500", limit=2))
        elif label == "coingecko":
            tasks[label] = lambda cg=coingecko: cg.get_prices(CoinGeckoPriceQuery(coin_ids=("bitcoin", "ethereum")))
        elif label == "deribit":
            tasks[label] = lambda d=deribit: d.get_futures_term_structure(DeribitFuturesCurveQuery(currency="BTC"))
        elif label == "polymarket_recession":
            tasks[label] = lambda p=pm: p.list_events(PolymarketEventQuery(slug_contains="recession", limit=3, active=True, closed=False))
        elif label == "polymarket_war":
            tasks[label] = lambda p=pm: p.list_events(PolymarketEventQuery(slug_contains="war", limit=3, active=True, closed=False))
        elif label == "polymarket_ai":
            tasks[label] = lambda p=pm: p.list_events(PolymarketEventQuery(slug_contains="ai", limit=3, active=True, closed=False))
        elif label == "web_vix":
            tasks[label] = lambda w=web: w.search(WebSearchQuery(query="VIX current level 2026", max_results=3))
        elif label == "web_hy":
            tasks[label] = lambda w=web: w.search(WebSearchQuery(query="US high yield bond spread OAS 2026", max_results=3))
        elif label == "web_cds":
            tasks[label] = lambda w=web: w.search(WebSearchQuery(query="sovereign CDS spread current", max_results=3))
        elif label == "web_search":
            tasks[label] = lambda w=web: w.search(WebSearchQuery(query="market volatility risk indicators 2026", max_results=3))
        elif label == "yf_options":
            def _options_chain():
                yf = YFinanceProvider()
                return yf.get_chain(OptionsChainQuery(ticker="SPY"))
            tasks[label] = _options_chain

        # ---- New providers (added for richer reports) ----
        elif label == "tips_real_yield":
            tasks[label] = lambda t=treasury: t.latest_yield_curve(YieldCurveQuery(curve_kind="real"))
        elif label == "vix_direct":
            tasks[label] = lambda y=yahoo: y.get_history(PriceHistoryQuery(symbol="^VIX", limit=30))
        elif label == "dxy":
            tasks[label] = lambda y=yahoo: y.get_history(PriceHistoryQuery(symbol="DX-Y.NYB", limit=60))
        elif label == "eurusd":
            tasks[label] = lambda y=yahoo: y.get_history(PriceHistoryQuery(symbol="EURUSD=X", limit=60))
        elif label == "cftc_copper":
            tasks[label] = lambda c=cftc: c.list_reports(CftcCotQuery(commodity_name="COPPER", limit=2))
        elif label == "cftc_oil":
            tasks[label] = lambda c=cftc: c.list_reports(CftcCotQuery(commodity_name="CRUDE OIL", limit=2))
        elif label == "bis_rates":
            tasks[label] = lambda b=bis: b.get_policy_rates(BisRateQuery(countries=("US", "CN", "EU"), start_year=2020))
        elif label == "bis_credit_gap":
            tasks[label] = lambda b=bis: b.get_credit_to_gdp(BisCreditGapQuery(countries=("US", "CN"), start_year=2015))
        elif label == "cme_fedwatch":
            def _fedwatch():
                try:
                    fw = CMEFedWatchProvider()
                    return fw.get_probabilities()
                except Exception as e:
                    return {"error": f"CME FedWatch unavailable (may need proxy): {e}"}
            tasks[label] = _fedwatch
        elif label == "kalshi_fed":
            def _kalshi_fed():
                try:
                    k = KalshiProvider()
                    return k.list_markets(KalshiMarketQuery(series_ticker="KXFED", status="open", limit=10))
                except Exception as e:
                    return {"error": f"Kalshi unavailable (may need proxy): {e}"}
            tasks[label] = _kalshi_fed

    return tasks


# ---------------------------------------------------------------------------
# Progress posting
# ---------------------------------------------------------------------------

def _post(queue: Queue | None, event: str, data: dict) -> None:
    if queue:
        queue.put({"event": event, "data": data})


def run_fetch(question: str, queue: Queue | None = None) -> dict[str, Any]:
    labels = select_provider_labels(question)
    tasks = build_tasks(labels)

    _post(queue, "progress", {
        "step": 1,
        "message": f"理解问题: {question[:80]}",
        "provider_count": len(labels),
    })

    _post(queue, "progress", {
        "step": 2,
        "message": f"并行拉取 {len(labels)} 个数据源...",
    })

    for label in labels:
        _post(queue, "progress", {
            "step": 2,
            "provider": label,
            "status": "started",
        })

    result = gather(tasks, timeout_seconds=60)

    for label in labels:
        if label in result.errors:
            _post(queue, "progress", {
                "step": 2,
                "provider": label,
                "status": "error",
                "error": str(result.errors[label]),
            })
        elif label in result.results:
            data = result.results[label]
            if isinstance(data, dict) and "error" in data:
                _post(queue, "progress", {
                    "step": 2,
                    "provider": label,
                    "status": "error",
                    "error": str(data["error"]),
                })
            else:
                _post(queue, "progress", {
                    "step": 2,
                    "provider": label,
                    "status": "done",
                })
        else:
            _post(queue, "progress", {
                "step": 2,
                "provider": label,
                "status": "error",
                "error": "no result",
            })

    serialized: dict[str, Any] = {}
    for label in labels:
        data = result.results.get(label)
        if label in result.errors:
            serialized[label] = {"error": str(result.errors[label])}
        elif isinstance(data, dict) and "error" in data:
            serialized[label] = data
        elif data is not None:
            try:
                serialized[label] = _serialize(data)
            except Exception as exc:
                serialized[label] = {"error": f"serialization failed: {exc}"}
        else:
            serialized[label] = {"error": "no result"}

    return {"question": question, "results": serialized, "provider_labels": labels}
