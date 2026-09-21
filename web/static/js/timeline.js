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
  const trendCards = document.querySelector("#trend-cards");
  const trendChart = document.querySelector("#trend-chart");
  const trendFeed = document.querySelector("#trend-event-feed");
  const health = document.querySelector("#automation-health");
  const divergence = document.querySelector("#trend-divergence");
  const toggles = document.querySelector("#track-toggles");
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
    return item.subject_judgments?.[subject.value]?.direction || "unknown";
  }
  function directionLabel(direction) {
    return { strong_bullish: "明确看多", bullish: "偏多", bearish: "偏空", strong_bearish: "明确看空", neutral: "震荡或修复", mixed: "短中期分歧", unknown: "未判定", not_applicable: "需按会议比较" }[direction] || "未判定";
  }
  const horizonNames = { short: "短线", swing: "波段", medium: "中期" };
  const eventNames = { initiated: "首次建立", continued: "延续", strengthened: "增强", weakened: "减弱", shifted: "转向", reversed: "反转" };
  const directionScores = { strong_bullish: 2, bullish: 1, neutral: 0, bearish: -1, strong_bearish: -2 };
  function renderStructured(data) {
    const stateByHorizon = new Map(data.current_state.map((item) => [item.horizon, item]));
    trendCards.replaceChildren();
    for (const horizon of ["short", "swing", "medium"]) {
      const state = stateByHorizon.get(horizon);
      const card = node("article", `trend-card ${state?.direction || "empty"}`, "");
      card.append(node("span", "period", horizonNames[horizon]));
      card.append(node("strong", "", state ? directionLabel(state.direction) : "尚未建立"));
      card.append(node("p", "", state ? `置信度 ${state.confidence}% · 连续 ${state.streak} 次` : "下一份合规报告将建立基准"));
      card.append(node("p", "", state?.summary || "本次没有该周期的结构化结论"));
      trendCards.append(card);
    }
    health.textContent = data.automation_health.publications
      ? `自动入库正常 · ${data.automation_health.publications} 次发布`
      : "等待首份结构化报告";
    health.classList.toggle("warning", !data.automation_health.publications);
    const scores = data.current_state.map((item) => directionScores[item.direction]).filter(Number.isFinite);
    const split = scores.some((score) => score > 0) && scores.some((score) => score < 0);
    divergence.hidden = !split;
    divergence.textContent = split ? "周期分化：短线、波段和中期的方向并不一致，请按各自期限理解。" : "";
    drawTrendTracks(data.trend_points);
    trendFeed.replaceChildren();
    const meaningful = data.trend_events.filter((event) => event.event_type !== "continued").slice().reverse();
    meaningful.forEach((event) => {
      const item = node("article", `trend-event ${event.event_type}`, "");
      item.append(node("strong", "", `${horizonNames[event.horizon]} · ${eventNames[event.event_type] || event.event_type}`));
      item.append(node("p", "", `${directionLabel(event.old_direction)} → ${directionLabel(event.new_direction)} · 置信度 ${event.new_confidence}% · 连续 ${event.streak} 次`));
      item.addEventListener("click", () => showReport(event.report_hash));
      trendFeed.append(item);
    });
    if (!meaningful.length) trendFeed.append(node("p", "empty", data.trend_points.length ? "最近没有实质方向变化。" : "暂无结构化趋势事件。"));
  }
  function drawTrendTracks(points) {
    trendChart.replaceChildren(); toggles.replaceChildren();
    if (!points.length) { trendChart.append(node("p", "empty chart-placeholder", "该主题尚无结构化趋势数据；旧报告仍可在下方查看。")); return; }
    const enabled = new Set(["short", "swing", "medium"]);
    for (const horizon of enabled) {
      const label = node("label", "", ""); const checkbox = document.createElement("input"); checkbox.type = "checkbox"; checkbox.checked = true;
      checkbox.addEventListener("change", () => { checkbox.checked ? enabled.add(horizon) : enabled.delete(horizon); paint(); });
      label.append(checkbox, document.createTextNode(horizonNames[horizon])); toggles.append(label);
    }
    const paint = () => {
      trendChart.replaceChildren(); const width = Math.max(800, points.length * 80 + 160); const height = 300;
      const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, width, height, "aria-label": "三周期趋势曲线" });
      const y = (score) => 45 + (2 - score) * 48; const dates = [...new Set(points.map((p) => p.analysis_at))]; const x = (date) => 105 + dates.indexOf(date) * ((width - 160) / Math.max(1, dates.length - 1));
      for (const score of [2,1,0,-1,-2]) { svg.append(svgNode("line", { x1: 90, y1: y(score), x2: width-30, y2: y(score), class: "grid" })); svg.append(svgNode("text", { x: 10, y: y(score)+4 }, `${score > 0 ? "+" : ""}${score} ${directionLabel(Object.keys(directionScores).find((key) => directionScores[key] === score))}`)); }
      for (const horizon of enabled) {
        const series = points.filter((p) => p.horizon === horizon && Number.isFinite(directionScores[p.direction]));
        if (series.length > 1) svg.append(svgNode("polyline", { points: series.map((p) => `${x(p.analysis_at)},${y(directionScores[p.direction])}`).join(" "), class: `trend-line ${horizon}` }));
        series.forEach((p) => { const dot = circle({ cx:x(p.analysis_at), cy:y(directionScores[p.direction]), r:8, fill:horizon === "short" ? "#ffb66e" : horizon === "swing" ? "#73d9bb" : "#9f8df3" }, { ...p, title:`${horizonNames[horizon]} ${directionLabel(p.direction)}`, hash:p.report_hash }, "trend-point", p.summary); svg.append(dot); });
      }
      trendChart.append(svg);
    };
    paint();
  }
  function reviewReasons(item) {
    const reasons = [];
    if (item.subjects.length > 1) reasons.push("联合主题，需按资产拆分结论");
    if (!item.subjects.length) reasons.push("主题未识别");
    if (!item.analysis_at) reasons.push("分析时间缺失");
    if (!item.horizon) reasons.push("预测窗口缺失或不唯一");
    if (!item.summary) reasons.push("结论未识别");
    if (!reasons.length && item.extraction_status !== "confirmed") reasons.push("其他字段需核对");
    return reasons;
  }
  function circle(attrs, item, className, hint) {
    const el = svgNode("circle", { ...attrs, class: className, tabindex: 0, role: "button", "aria-label": `${item.title}，点击查看原文` });
    el.append(svgNode("title", {}, `${item.title}\n${item.analysis_at || "时间待核对"}${hint ? `\n${hint}` : ""}`));
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
    const policy = subject.value === "美联储";
    const chartHeight = policy ? 230 : 292;
    const svg = svgNode("svg", { viewBox: `0 0 ${width} ${chartHeight}`, width, height: chartHeight, "aria-label": `${subject.value}判断节点图` });
    const positions = policy ? { not_applicable: 112 } : { bullish: 45, neutral: 91, mixed: 137, bearish: 183, unknown: 229 };
    const colors = { bullish: "#5cddac", neutral: "#e6c776", mixed: "#b6a3f5", bearish: "#ff918f", unknown: "#8496ae", not_applicable: "#91b9fc" };
    for (const [direction, y] of Object.entries(positions)) {
      svg.append(svgNode("line", { x1: 78, y1: y, x2: width - 30, y2: y, class: "grid" }));
      svg.append(svgNode("text", { x: 12, y: y + 4, class: "chart-label" }, policy ? "按会议比较" : directionLabel(direction)));
    }
    dated.forEach((item, index) => {
      const direction = stance(item);
      const evidence = item.subject_judgments?.[subject.value]?.evidence || (direction === "not_applicable" ? "需按议息会议和预测期限比较加息概率" : "未找到该主题的独立结论");
      svg.append(circle({ cx: x(index), cy: positions[direction] ?? positions.unknown ?? positions.not_applicable, r: 10, fill: colors[direction] || colors.unknown, "data-hash": item.hash, "data-direction": direction }, item, "report-node", `${directionLabel(direction)}：${evidence}`));
      svg.append(svgNode("text", { x: x(index), y: policy ? 208 : 274, "text-anchor": "middle" }, item.analysis_at.slice(5, 16).replace("T", " ")));
    });
    svg.append(svgNode("line", { x1: 78, y1: policy ? 187 : 250, x2: width - 30, y2: policy ? 187 : 250, class: "axis" }));
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
    renderStructured(data);
    document.querySelector("#direction-note").textContent = selected === "美联储"
      ? "美联储报告讨论不同议息会议的加息概率，不能画在资产偏多偏空轴上；需按会议和预测期限分别比较。点击节点查看原文。"
      : "节点读取当前主题在原报告中的结论；方向与概率是否可比是两回事。短中期观点冲突时标为分歧。点按分析时间排序，间距不代表日历天数；点击可查看原文。";
    count.textContent = selected
      ? `${data.reports.length} 份匹配报告 · 联合分析 ${data.counts.matching_joint} 份 · 单主题需补字段 ${data.counts.matching_single_needs_review} 份（全库待整理 ${data.counts.needs_review} 份）`
      : `${data.reports.length} 份报告 · ${data.counts.needs_review} 份待整理`;
    const dated = data.reports.filter((item) => item.analysis_at).sort((a, b) => a.analysis_at.localeCompare(b.analysis_at));
    const unknown = data.reports.filter((item) => !item.analysis_at).sort((a, b) => (b.source_time_hint || "").localeCompare(a.source_time_hint || ""));
    document.querySelector("#stat-reports").textContent = data.reports.length;
    document.querySelector("#stat-dated").textContent = dated.length;
    document.querySelector("#stat-direction").textContent = dated.filter((item) => !["unknown", "not_applicable"].includes(stance(item))).length;
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
      const judgment = item.subject_judgments?.[selected];
      const summary = node("p", "summary", judgment?.evidence ? judgment.evidence : item.summary || "结论待核对；点击查看原报告");
      if (selected) card.append(node("p", "subject-judgment", `${selected}判断：${directionLabel(judgment?.direction)}${judgment?.source_line ? ` · 原文第 ${judgment.source_line} 行` : ""}${judgment?.direction === "unknown" ? " · 原文未给出明确的单项方向" : ""}`));
      const detail = node("div", "detail", `${item.subjects.join(" / ") || "主题待核对"} · ${item.horizon || "窗口待核对"} · ${item.market_session === "intraday" ? "盘中" : item.market_session === "close" ? "收盘" : "口径待核对"} · ${item.main_probability == null ? "概率待核对" : `主情景 ${item.main_probability}%`}`);
      const joint = item.subjects.length > 1;
      const ready = !joint && item.extraction_status === "confirmed";
      const quality = node("span", ready ? "quality confirmed" : "quality review", joint ? "联合分析" : ready ? "字段已识别" : "需补字段");
      card.append(date, heading, summary, detail, quality);
      if (!ready) card.append(node("p", "review-reasons", reviewReasons(item).join("；")));
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
