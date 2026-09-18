"""Read asset-specific direction from an explicit report conclusion."""
from __future__ import annotations

import re


def _excerpt(summary: str, subject: str, subjects: list[str]) -> str:
    clean = re.sub(r"[*`>]", "", summary).strip(" -\t")
    if len(subjects) > 1:
        start = clean.find(subject)
        if start < 0:
            return ""
        clean = clean[start:]
        ends = [clean.find(other, len(subject)) for other in subjects if other != subject]
        ends = [position for position in ends if position >= 0]
        if ends:
            clean = clean[:min(ends)]
    return re.split(r"[。；]", clean, maxsplit=1)[0].strip(" ，、:：-\t")


def _direction(excerpt: str) -> tuple[str, int | None]:
    if not excerpt:
        return "unknown", None
    # A negated advance is not a positive forecast.
    text = re.sub(r"(?:不是|不再|不会|不能|不宜|未能|未形成|不足以|不代表|不意味着).{0,8}(?:上攻|上行|上涨|偏多|偏强)", "", excerpt)
    bullish = bool(re.search(r"偏多|偏强|走强|上调为|突破加速|上升趋势|上涨趋势|上行趋势|多头结构|牛市", text))
    bearish = bool(re.search(r"偏空|偏弱|转弱|承压|下跌|下探|回撤|回调|走弱|弱势|空头趋势", text))
    if bullish and bearish:
        return "mixed", None
    if bullish:
        return "bullish", 2 if re.search(r"短线偏多|上调为|突破加速", text) else 1
    if bearish:
        return "bearish", -1
    if re.search(r"震荡|横盘|筑底|修复|反弹|观望|区间", text):
        return "neutral", 0
    return "unknown", None


def subject_judgments(summary: str | None, subjects: list[str], source_line: int | None) -> dict:
    judgments = {}
    for subject in subjects:
        evidence = _excerpt(summary or "", subject, subjects)
        direction, score = _direction(evidence)
        judgments[subject] = {"direction": direction, "score": score, "evidence": evidence, "source_line": source_line}
    return judgments
