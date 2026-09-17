(function () {
  "use strict";
  const subject = document.querySelector("#subject");
  const timeline = document.querySelector("#timeline");
  const changes = document.querySelector("#changes");
  const count = document.querySelector("#count");
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
    timeline.replaceChildren();
    changes.replaceChildren();
    const rows = data.reports.filter((x) => x.analysis_at).reverse().concat(data.reports.filter((x) => !x.analysis_at).reverse());
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
