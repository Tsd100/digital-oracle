(function () {
  "use strict";
  const subject = document.querySelector("#subject");
  const timeline = document.querySelector("#timeline");
  const changes = document.querySelector("#changes");
  const count = document.querySelector("#count");
  const reportChart = document.querySelector("#report-chart");
  const probabilityChart = document.querySelector("#probability-chart");
  const probabilityNote = document.querySelector("#probability-note");
  const undated = document.querySelector("#undated");
  const dialog = document.querySelector("#report-dialog");
  const title = document.querySelector("#dialog-title");
  const source = document.querySelector("#dialog-source");
  const content = document.querySelector("#dialog-content");
  const params = new URLSearchParams(location.search);
  if (params.get("subject")) subject.value = params.get("subject");
  document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());

  function node(tag, className, text) {
    const el = document.createElement(tag);
    el.className = className;
    el.textContent = text;
    return el;
  }
  const SVG_NS = "http://www.w3.org/2000/svg";
  function svgNode(tag, attrs, value) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs || {}).forEach(([key, val]) => el.setAttribute(key, String(val)));
    if (value !== undefined) el.textContent = value;
    return el;
  }
  function stance(item) {
    if (item.extraction_status !== "confirmed" || item.subjects.length !== 1) return "review";
    if (/偏空|转弱|回撤风险上升/.test(item.summary || "")) return "bearish";
    if (/偏多|偏强|上调为|突破加速/.test(item.summary || "")) return "bullish";
    return "review";
  }
  function circle(attrs, item, className) {
    const el = svgNode("circle", { ...attrs, class: className, tabindex: 0, role: "button", "aria-label": `${item.title}，点击查看原文` });
    el.append(svgNode("title", {}, `${item.title}\n${item.analysis_at || "时间待核对"}`));
    el.addEventListener("click", () => showReport(item.hash));
    el.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); showReport(item.hash); }
    });
    return el;
  }
  function geometry(dated) {
    const width = Math.max(800, dated.length * 90 + 130);
    return { width, x: (index) => 92 + index * ((width - 147) / Math.max(1, dated.length - 1)) };
  }
  function drawReportChart(dated, unknown) {
    reportChart.replaceChildren();
    undated.replaceChildren();
    if (!subject.value) { reportChart.append(node("p", "empty chart-placeholder", "选择一个主题查看报告节点。")); return; }
    if (!dated.length) { reportChart.append(node("p", "empty chart-placeholder", "该主题没有明确分析时间的报告。")); return; }
    const { width, x } = geometry(dated);
    const svg = svgNode("svg", { viewBox: `0 0 ${width} 230`, width, height: 230, "aria-label": `${subject.value}报告节点图` });
    for (const [name, y] of [["偏多", 57], ["待核对", 112], ["偏空", 167]]) {
      svg.append(svgNode("line", { x1: 78, y1: y, x2: width - 30, y2: y, class: "grid" }));
      svg.append(svgNode("text", { x: 16, y: y + 4, class: "chart-label" }, name));
    }
    dated.forEach((item, index) => {
      const direction = stance(item);
      const y = direction === "bullish" ? 57 : direction === "bearish" ? 167 : 112;
      const fill = direction === "bullish" ? "#5cddac" : direction === "bearish" ? "#ff918f" : "#8496ae";
      svg.append(circle({ cx: x(index), cy: y, r: 10, fill, "data-hash": item.hash }, item, "report-node"));
      svg.append(svgNode("text", { x: x(index), y: 208, "text-anchor": "middle" }, item.analysis_at.slice(5, 16).replace("T", " ")));
    });
    svg.append(svgNode("line", { x1: 78, y1: 187, x2: width - 30, y2: 187, class: "axis" }));
    reportChart.append(svg);
    if (unknown.length) {
      const details = node("details", "", "");
      details.append(node("summary", "", `${unknown.length} 份报告的分析时间待核对；查看文件名时间线索`));
      for (const item of unknown) {
        const button = node("button", "", `${item.source_time_hint || "未知"} · ${item.title}`);
        button.addEventListener("click", () => showReport(item.hash));
        details.append(button);
      }
      undated.append(details);
    }
  }
  function drawProbabilityChart(dated, pairs) {
    probabilityChart.replaceChildren();
    probabilityNote.textContent = "";
    const valid = dated.filter((item) => item.subjects.length === 1 && item.horizon && item.scenarios?.length && Number.isFinite(item.main_probability));
    const comparable = pairs.filter((pair) => pair.main_probability_delta !== null);
    document.querySelector("#probability-count").textContent = `${valid.length} 个概率点 · ${comparable.length} 段可比连线`;
    if (!subject.value) { probabilityChart.append(node("p", "empty chart-placeholder", "选择主题后查看可比概率。")); return; }
    if (!valid.length) { probabilityChart.append(node("p", "empty chart-placeholder", "暂无可单独展示的主情景概率。")); return; }
    const { width, x } = geometry(dated);
    const y = (prob) => 30 + (100 - prob) * 1.55;
    const svg = svgNode("svg", { viewBox: `0 0 ${width} 230`, width, height: 230, "aria-label": `${subject.value}主情景概率图` });
    for (const value of [100, 75, 50, 25, 0]) {
      svg.append(svgNode("line", { x1: 78, y1: y(value), x2: width - 30, y2: y(value), class: "grid" }));
      svg.append(svgNode("text", { x: 20, y: y(value) + 4 }, `${value}%`));
    }
    const indexed = new Map(dated.map((item, index) => [item.hash, { item, index }]));
    for (const pair of comparable) {
      const a = indexed.get(pair.old_hash);
      const b = indexed.get(pair.new_hash);
      if (!a || !b || !valid.includes(a.item) || !valid.includes(b.item)) continue;
      svg.append(svgNode("line", { x1: x(a.index), y1: y(a.item.main_probability), x2: x(b.index), y2: y(b.item.main_probability), class: "prob-segment" }));
    }
    for (const item of valid) {
      const index = indexed.get(item.hash).index;
      svg.append(circle({ cx: x(index), cy: y(item.main_probability), r: 7, fill: "#73d9bb", "data-hash": item.hash }, item, "prob-point"));
      svg.append(svgNode("text", { x: x(index), y: y(item.main_probability) - 13, "text-anchor": "middle" }, `${item.main_probability}%`));
    }
    probabilityChart.append(svg);
    if (valid.length) probabilityChart.scrollLeft = Math.max(0, x(indexed.get(valid[0].hash).index) - probabilityChart.clientWidth / 2);
    if (!comparable.length) probabilityNote.textContent = "当前没有满足同主题、同预测窗口和同情景定义的连续概率记录，因此不连线。";
  }
  async function showReport(hash) {
    const res = await fetch(`/api/timeline/report/${encodeURIComponent(hash)}`);
    if (!res.ok) return;
    const data = await res.json();
    title.textContent = data.title;
    source.textContent = data.sources.join(" · ");
    content.textContent = data.content;
    dialog.showModal();
  }
  async function refresh() {
    const selected = subject.value;
    const res = await fetch(`/api/timeline?subject=${encodeURIComponent(selected)}`);
    const data = await res.json();
    count.textContent = `${data.reports.length} 份匹配报告 · ${data.counts.needs_review} 份全库待核对`;
    const dated = data.reports.filter((item) => item.analysis_at).sort((a, b) => a.analysis_at.localeCompare(b.analysis_at));
    const unknown = data.reports.filter((item) => !item.analysis_at).sort((a, b) => (b.source_time_hint || "").localeCompare(a.source_time_hint || ""));
    document.querySelector("#stat-reports").textContent = data.reports.length;
    document.querySelector("#stat-dated").textContent = dated.length;
    document.querySelector("#stat-segments").textContent = data.changes.filter((pair) => pair.main_probability_delta !== null).length;
    document.querySelector("#report-list-count").textContent = `（${data.reports.length} 份）`;
    document.querySelector("#change-list-count").textContent = `（${data.changes.length} 组）`;
    drawReportChart(dated, unknown);
    drawProbabilityChart(dated, data.changes);
    timeline.replaceChildren();
    changes.replaceChildren();
    const rows = dated.slice().reverse().concat(unknown);
    for (const item of rows) {
      const card = node("article", "report-card", "");
      const date = node("div", "date", item.analysis_at ? item.analysis_at.replace("T", " ").slice(0, 16) : `分析时间待核对${item.source_time_hint ? ` · 文件名时间 ${item.source_time_hint}` : ""}`);
      const heading = node("button", "report-title", item.title);
      heading.addEventListener("click", () => showReport(item.hash));
      const summary = node("p", "summary", item.summary || "结论待核对；点击查看原报告");
      const detail = node("div", "detail", `${item.subjects.join(" / ") || "主题待核对"} · ${item.horizon || "窗口待核对"} · ${item.market_session === "intraday" ? "盘中" : item.market_session === "close" ? "收盘" : "口径待核对"} · ${item.main_probability == null ? "概率待核对" : `主情景 ${item.main_probability}%`}`);
      const quality = node("span", item.extraction_status === "confirmed" ? "quality confirmed" : "quality review", item.extraction_status === "confirmed" ? "已识别" : "待核对");
      card.append(date, heading, summary, detail, quality);
      timeline.append(card);
    }
    if (!rows.length) timeline.append(node("p", "empty", "暂无匹配报告。"));
    for (const change of data.changes.slice().reverse()) {
      const old = data.reports.find((x) => x.hash === change.old_hash);
      const next = data.reports.find((x) => x.hash === change.new_hash);
      const item = node("article", "change-card", "");
      item.append(node("div", "date", `${old.analysis_at?.slice(0, 16) || "未知"} → ${next.analysis_at?.slice(0, 16) || "未知"}`));
      item.append(node("strong", "", `判断：${change.judgment_change}`));
      item.append(node("p", "", change.main_probability_delta == null ? `主情景概率不可直接比较：${change.comparability}` : `主情景概率 ${change.main_probability_delta >= 0 ? "+" : ""}${change.main_probability_delta} 个百分点`));
      if (change.session_changed) item.append(node("p", "warning", "盘中 / 收盘口径发生变化"));
      changes.append(item);
    }
    if (!data.changes.length) changes.append(node("p", "empty", selected ? "暂无可直接比较的连续报告；时间或预测窗口可能待核对。" : "选择一个主题查看变化。"));
  }
  subject.addEventListener("change", () => { history.replaceState(null, "", subject.value ? `?subject=${encodeURIComponent(subject.value)}` : "/timeline"); refresh(); });
  refresh().catch((error) => { timeline.textContent = `时间线加载失败：${error.message}`; });
})();
