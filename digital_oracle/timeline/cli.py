"""Command line entry point for DO report history."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from . import TimelineStore, compare_subject, import_sources, publish_report
from .store import DEFAULT_ARCHIVE, DEFAULT_DB


def render_comparison(subject: str, result: dict) -> str:
    lines = [f"# {subject}：DO 历史判断变化", "", "| 分析时间 | 报告 | 结论 | 主情景 | 数据口径 | 状态 |", "|---|---|---|---:|---|---|"]
    for item in result["reports"]:
        summary = (item.get("summary") or "待核对").replace("|", "／")
        if len(summary) > 100:
            summary = summary[:100] + "…"
        prob = item.get("main_probability")
        source = item.get("sources", [""])[0] if item.get("sources") else ""
        probability = f"{prob:g}%" if prob is not None else "待核对"
        lines.append(f"| {item.get('analysis_at') or '时间待核对'} | {item['title']} | {summary} | {probability} | {item.get('market_session', 'unknown')} | {item.get('extraction_status', 'needs_review')} |")
        lines.append(f"<!-- source: {source}; hash: {item.get('hash', '')}; summary_line: {item.get('summary_line')} -->")
    lines += ["", "## 逐次变化（仅比较有明确分析时间的报告）", ""]
    for pair in result["pairs"]:
        old, new = pair["old"], pair["new"]
        delta = pair["main_probability_delta"]
        probability = "不可直接比较" if delta is None else f"{delta:+g} 个百分点"
        lines.append(f"- {old.get('analysis_at') or '未知'} → {new.get('analysis_at') or '未知'}：判断{pair['judgment_change']}；主情景概率{probability}；{pair['comparability']}。" + (" 数据口径发生变化。" if pair["session_changed"] else ""))
        lines.append(f"  - 原文：{old.get('sources', [''])[0]}；{new.get('sources', [''])[0]}")
    if not result["reports"]:
        lines.append("暂无匹配报告。")
    lines += ["", "*历史判断只代表当时报告；当前走势须另行获取最新行情。*"]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="DO 历史分析时间线")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    imp = sub.add_parser("import", help="只读导入报告来源")
    imp.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    imp.add_argument("--reports", type=Path, default=Path(__file__).resolve().parents[2] / "reports")
    imp.add_argument("--web-db", type=Path, default=Path(__file__).resolve().parents[2] / "web" / "digital_oracle.db")
    for command in ("list", "compare"):
        sub_parser = sub.add_parser(command)
        sub_parser.add_argument("--subject", required=True)
        sub_parser.add_argument("--limit", type=int, default=100)
    correction = sub.add_parser("correct")
    correction.add_argument("--hash", required=True)
    correction.add_argument("--field", required=True)
    correction.add_argument("--value", required=True, help="JSON value")
    publish = sub.add_parser("publish", help="发布带 do-trend 数据块的新报告")
    publish.add_argument("report", type=Path)
    publish.add_argument("--source-key")
    publish.add_argument("--source-kind", default="file")
    args = parser.parse_args(argv)
    if args.command == "import":
        print(json.dumps(import_sources(args.db, [args.reports, args.archive], args.web_db), ensure_ascii=False, indent=2))
        return
    store = TimelineStore(args.db)
    if args.command == "publish":
        path = args.report.resolve()
        result = publish_report(store, args.source_key or str(path), path.read_text(encoding="utf-8-sig"), args.source_kind)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return
    if args.command == "correct":
        store.correct(args.hash, args.field, json.loads(args.value))
        print("校正已记录")
        return
    rows = store.list_reports(args.subject, args.limit)
    if args.command == "list":
        for row in rows:
            print(f"{row['analysis_at'] or '未知时间'}\t{row['title']}\t{row['hash'][:12]}\t{row['extraction_status']}")
    else:
        print(render_comparison(args.subject, compare_subject(rows, args.subject)))


if __name__ == "__main__":
    main()
