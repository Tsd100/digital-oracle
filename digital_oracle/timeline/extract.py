"""Conservative extraction of comparable fields from historical DO reports."""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta

CN = timezone(timedelta(hours=8))
PARSER_VERSION = 1

TOPIC_PATTERNS = {
    "有色": (r"有色", r"non.?ferrous"),
    "科创50": (r"科创\s*50", r"star\s*50"),
    "半导体": (r"半导体", r"semiconductor"),
    "黄金": (r"黄金", r"金价", r"\bgold\b"),
    "白银": (r"白银", r"银价", r"\bsilver\b"),
    "原油": (r"原油", r"油价", r"\boil\b"),
    "创新药": (r"创新药", r"医药"),
    "光模块": (r"光模块", r"CPO"),
    "美联储": (r"美联储", r"联储", r"\bFed\b"),
}


def _first(pattern: str, text: str, flags: int = re.I) -> str | None:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else None


def _analysis_time(text: str) -> str | None:
    patterns = [
        r"分析时间（北京时间）\*{0,2}\s*[：:]\s*(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})日?\s*(\d{1,2}):(\d{2})",
        r"(?:确认北京时间|分析时间|北京时间)\*{0,2}\s*[：:]\s*(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})日?\s*(\d{1,2}):(\d{2})",
        r"(?:报告时间|生成时间)\*{0,2}\s*[：:]\s*(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})日?\s*(\d{1,2}):(\d{2})",
        r"报告日期\*{0,2}[：:]\s*(\d{4})[-年/](\d{1,2})[-月/](\d{1,2})日?\s*(\d{1,2}):(\d{2})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            try:
                return datetime(*map(int, m.groups()), tzinfo=CN).isoformat(timespec="minutes")
            except ValueError:
                return None
    return None


def _section(text: str, name: str) -> str:
    m = re.search(rf"^##\s*(?:[一二三四五六七八九十0-9]+[、.]\s*)?{name}.*$", text, re.M | re.I)
    if not m:
        return ""
    rest = text[m.end():]
    end = re.search(r"^##\s", rest, re.M)
    return rest[:end.start()] if end else rest


def _topics(title: str, conclusion: str) -> list[str]:
    # Topic discovery uses the title; a broad report's data table can mention unrelated assets.
    result = [name for name, pats in TOPIC_PATTERNS.items() if any(re.search(p, title, re.I) for p in pats)]
    if not result:
        result = [name for name, pats in TOPIC_PATTERNS.items() if any(re.search(p, conclusion[:300], re.I) for p in pats)]
    return result


def extract_report(text: str) -> dict:
    lines = text.splitlines()
    title = next((line.lstrip("# ").strip() for line in lines if line.startswith("# ")), "未命名报告")
    conclusion = _section(text, "结论") or _section(text, "Conclusion")
    if not conclusion:
        conclusion = _section(text, "一句话结论") or _section(text, "结论先行")
    quote = next((line.lstrip("> ").strip("* ") for line in conclusion.splitlines() if line.lstrip().startswith(">")), None)
    summary = quote or next((line.strip("* ") for line in conclusion.splitlines() if line.strip() and not line.startswith("#")), None)
    horizon = _first(r"(?:分析窗口|情景（未来|情景\(未来)[：:]?\s*(?:未来)?\s*(\d+\s*[—–-]\s*\d+\s*(?:周|月|年|个交易日))", text)
    if not horizon:
        horizon = _first(r"(?:未来|近期[（(])\s*(\d+\s*[—–-]\s*\d+\s*(?:周|月|年|个交易日))", text[:1800])
    horizon = re.sub(r"\s+", "", horizon) if horizon else None
    scenario_section = _section(text, "情景概率") or _section(text, "概率估计") or _section(text, "Probability Estimates")
    scenarios = []
    for line in scenario_section.splitlines():
        cells = [c.strip(" *") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and re.fullmatch(r"\d+(?:\.\d+)?\s*%", cells[1]):
            scenarios.append({"label": cells[0], "probability": float(cells[1].rstrip("%")), "evidence": cells[2] if len(cells) > 2 else ""})
    threshold_section = _section(text, "结论")
    threshold_rows = []
    for line in threshold_section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 4 and cells[0] not in ("信号", "---") and not cells[0].startswith("-") and "阈值" not in cells[0]:
            if re.search(r"\d", cells[2]):
                threshold_rows.append({"signal": cells[0], "current": cells[1], "threshold": cells[2], "meaning": cells[3]})
    data_note = next((l.lstrip("> ").strip() for l in lines if "数据口径" in l or "数据截止" in l), None)
    session = "intraday" if (data_note and "盘中" in data_note) or "盘中数据" in text[:600] else "close" if "收盘" in text[:600] else "unknown"
    subjects = _topics(title, conclusion)
    quality = "confirmed" if _analysis_time(text) and horizon and summary and len(subjects) == 1 else "needs_review"
    return {
        "title": title, "subjects": subjects, "analysis_at": _analysis_time(text),
        "data_as_of": data_note, "market_session": session, "horizon": horizon,
        "summary": summary, "summary_line": next((i + 1 for i, line in enumerate(lines) if summary and summary in line), None),
        "main_probability": scenarios[0]["probability"] if scenarios else None,
        "scenarios": scenarios, "thresholds": threshold_rows, "extraction_status": quality,
        "parser_version": PARSER_VERSION,
    }
