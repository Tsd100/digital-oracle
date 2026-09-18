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
        ends = [match.start() for other in subjects if other != subject
                for match in re.finditer(rf"[；。、]\s*{re.escape(other)}", clean)]
        if ends:
            clean = clean[:min(ends)]
    return re.split(r"[。；]", clean, maxsplit=1)[0].strip(" ，、:：-\t")


def _explicit_candidates(report_text: str, subject: str):
    lines = report_text.splitlines()
    section = ""
    name = re.escape(subject) + ("(?:金属)?" if subject == "有色" else "")
    prefix = re.compile(rf"^{name}(?:判断)?(?:[：:]|$)")
    for index, raw in enumerate(lines):
        if raw.startswith("## "):
            section = raw
        if raw.lstrip().startswith("|"):
            continue
        clean = re.sub(r"[*`>]", "", raw).strip(" #\t-")
        clean = re.sub(r"^[一二三四五六七八九十\d]+[.、]\s*", "", clean)
        if not prefix.match(clean):
            continue
        is_heading = raw.lstrip().startswith("#")
        if not is_heading and not re.search(r"结论|判断|展望", section):
            continue
        candidate = re.split(r"[。；]", clean, maxsplit=1)[0].strip()
        yield candidate, index + 1
        if is_heading and re.fullmatch(rf"{name}判断?", clean):
            for following in range(index + 1, len(lines)):
                paragraph = lines[following].strip()
                if paragraph.startswith("#"):
                    break
                if paragraph and not paragraph.startswith("|"):
                    first_sentence = re.split(r"[。；]", re.sub(r"[*`>]", "", paragraph), maxsplit=1)[0].strip()
                    yield f"{subject}：{first_sentence}", following + 1
                    break


def _summary_candidates(summary: str, subject: str, subjects: list[str], source_line: int | None):
    first = _excerpt(summary, subject, subjects)
    if first:
        yield first, source_line
    if len(subjects) == 1:
        for sentence in re.split(r"[。；]", re.sub(r"[*`>]", "", summary))[1:]:
            sentence = sentence.strip(" ，、:：-\t")
            if sentence and re.search(r"未来|后续|本周|当前|短线|短期|中期|接下来|最可能|预计|判断|趋势|形态|反弹", sentence):
                yield sentence, source_line


def _conclusion_quote_candidates(report_text: str):
    section = ""
    for index, line in enumerate(report_text.splitlines(), 1):
        if line.startswith("## "):
            section = line
        if re.search(r"结论|判断", section) and line.lstrip().startswith(">"):
            sentence = re.split(r"[。；]", re.sub(r"[*`>]", "", line), maxsplit=1)[0].strip()
            if re.search(r"未来|后续|本周|当前|短线|短期|中期|接下来|最可能|预计|判断|趋势|反弹", sentence):
                yield sentence, index


def _scenario_candidate(report_text: str, subject: str):
    """Use a scenario label only when this asset has one explicit scenario table."""
    def unique_top(rows):
        highest = max(row[1] for row in rows)
        leaders = [row for row in rows if row[1] == highest]
        return leaders[0] if len(leaders) == 1 else None

    sections = []
    in_scenarios = False
    active = False
    rows = []
    for index, line in enumerate(report_text.splitlines(), 1):
        if line.startswith("## "):
            if active and rows:
                sections.append(unique_top(rows))
            in_scenarios = bool(re.search(r"概率|情景", line))
            active, rows = False, []
        elif line.startswith("### "):
            if active and rows:
                sections.append(unique_top(rows))
            active = in_scenarios and bool(re.match(rf"###\s+{re.escape(subject)}(?:\b|未来|[（(]|\s|$)", line))
            rows = []
        elif active and line.lstrip().startswith("|"):
            cells = [cell.strip(" *") for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and re.fullmatch(r"\d+(?:\.\d+)?\s*%", cells[1]):
                rows.append((cells[0], float(cells[1].rstrip("%")), index))
    if active and rows:
        sections.append(unique_top(rows))
    if len(sections) == 1 and sections[0] is not None:
        label, probability, line = sections[0]
        return f"{subject}：{label}（主情景 {probability:g}%）", line
    return None


def _direction(excerpt: str) -> tuple[str, int | None]:
    if not excerpt:
        return "unknown", None
    # A negated advance is not a positive forecast.
    text = re.sub(r"(?:不是|不再|不会|不能|不宜|未能|未形成|不足以|不代表|不意味着).{0,8}(?:上攻|上行|上涨|偏多|偏强)", "", excerpt)
    text = re.sub(r"只有.{0,80}?(?:才|方可).*$", "", text)
    text = re.sub(r"(?:回撤|下跌|下探)风险", "", text)
    bullish = bool(re.search(r"偏多|偏强|走强|上调为|突破加速|上升趋势|上涨趋势|上行趋势|中期涨势|长期涨势|多头结构|多头基础|牛市", text))
    bearish = bool(re.search(r"偏空|偏弱|转弱|承压|下跌|下探|短线跌势|短线.{0,6}更弱|回撤|回调|走弱|弱势|仍弱|空头趋势", text))
    if bullish and bearish:
        return "mixed", None
    if bullish:
        return "bullish", 2 if re.search(r"短线偏多|上调为|突破加速", text) else 1
    if bearish:
        return "bearish", -1
    if re.search(r"震荡|横盘|筑底|修复|反弹|观望|区间", text):
        return "neutral", 0
    return "unknown", None


def subject_judgments(summary: str | None, subjects: list[str], source_line: int | None, report_text: str = "") -> dict:
    judgments = {}
    for subject in subjects:
        if subject == "美联储":
            judgments[subject] = {"direction": "not_applicable", "score": None, "evidence": "", "source_line": None}
            continue
        candidates = list(_explicit_candidates(report_text, subject)) + list(_summary_candidates(summary or "", subject, subjects, source_line))
        if len(subjects) == 1:
            candidates += list(_conclusion_quote_candidates(report_text))
        scenario = _scenario_candidate(report_text, subject)
        if scenario:
            candidates.append(scenario)
        chosen = ("", source_line)
        direction, score = "unknown", None
        for evidence, line in candidates:
            if not chosen[0]:
                chosen = evidence, line
            direction, score = _direction(evidence)
            if direction != "unknown":
                chosen = evidence, line
                break
        else:
            direction, score = "unknown", None
        judgments[subject] = {"direction": direction, "score": score, "evidence": chosen[0], "source_line": chosen[1]}
    return judgments
