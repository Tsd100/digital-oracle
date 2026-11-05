(() => {
  "use strict";

  const directionLabels = {
    strong_bullish: "强势偏多", bullish: "偏多", neutral: "震荡或修复",
    mixed: "短中期分歧", bearish: "偏空", strong_bearish: "强势偏空",
    not_applicable: "不适用", unknown: "尚未判定",
  };
  const horizonLabels = { short: "短期", swing: "波段", medium: "中期" };
  const $ = (selector) => document.querySelector(selector);
  const node = (tag, className, text) => {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (text !== undefined) el.textContent = text;
    return el;
  };

  function directionLabel(value) { return directionLabels[value] || "尚未判定"; }
  function formatDate(value, withTime = false) {
    if (!value) return "尚无更新时间";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value.slice(0, withTime ? 16 : 10).replace("T", " ");
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit",
      hour: withTime ? "2-digit" : undefined, minute: withTime ? "2-digit" : undefined,
      hour12: false,
    }).format(parsed);
  }
  function dateKey(value) { return value ? value.slice(0, 10) : ""; }

  function setupTheme() {
    const button = $("#theme-toggle");
    const refresh = () => {
      const dark = document.documentElement.dataset.theme === "dark";
      button.textContent = dark ? "☀ 浅色" : "☾ 深色";
      button.setAttribute("aria-pressed", String(dark));
    };
    button.addEventListener("click", () => {
      const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      document.documentElement.dataset.theme = next;
      localStorage.setItem("do-timeline-theme", next);
      refresh();
    });
    refresh();
  }

  function renderMetrics(data) {
    const metrics = [
      ["跟踪主题", data.totals.subjects, "个"],
      ["历史研判", data.totals.reports, "份"],
      ["最近更新", formatDate(data.totals.latest_analysis_at, true), ""],
    ];
    const container = $("#overview-metrics");
    container.replaceChildren();
    metrics.forEach(([label, value, suffix]) => {
      const card = node("article", "metric");
      card.append(node("span", "metric-label", label));
      const strong = node("strong", "", String(value));
      if (suffix) strong.append(node("small", "", suffix));
      card.append(strong);
      container.append(card);
    });
  }

  function makeSignalCell(item, point) {
    const button = node("button", `signal-cell ${point.direction}`);
    button.type = "button";
    button.dataset.hash = point.hash || "";
    button.dataset.subject = item.name;
    button.dataset.direction = point.direction;
    button.dataset.analysisAt = point.analysis_at || "";
    button.dataset.evidence = point.evidence || "";
    button.setAttribute("aria-label", `${item.name}，${formatDate(point.analysis_at)}，${directionLabel(point.direction)}`);
    button.title = `${item.name} · ${formatDate(point.analysis_at)} · ${directionLabel(point.direction)}`;
    button.append(node("span", "signal-dot"));
    return button;
  }

  function renderHorizons(data) {
    const container = $("#horizon-matrix-content");
    container.replaceChildren();
    const table = node("table", "signal-table horizon-table");
    const head = node("thead");
    const headRow = node("tr");
    headRow.append(node("th", "subject-column", "主题"));
    ["short", "swing", "medium"].forEach((key) => headRow.append(node("th", "", horizonLabels[key])));
    headRow.append(node("th", "update-column", "更新时间"));
    head.append(headRow); table.append(head);
    const body = node("tbody");
    data.subjects.filter((item) => item.report_count > 0).forEach((item) => {
      const row = node("tr");
      const subject = node("th", "subject-column"); subject.scope = "row";
      const link = node("a", "subject-link", item.name); link.href = item.timeline_url; subject.append(link); row.append(subject);
      const byHorizon = Object.fromEntries(item.horizons.map((trend) => [trend.horizon, trend]));
      ["short", "swing", "medium"].forEach((key) => {
        const cell = node("td", "horizon-value");
        const trend = byHorizon[key];
        if (trend) {
          const badge = node("span", `matrix-badge ${trend.direction}`, directionLabel(trend.direction));
          badge.title = trend.evidence || "";
          cell.append(badge);
        } else {
          cell.append(node("span", "matrix-empty", "—"));
        }
        row.append(cell);
      });
      row.append(node("td", "update-column", formatDate(item.latest_analysis_at, true)));
      body.append(row);
    });
    table.append(body); container.append(table);
  }

  function renderHistory(data) {
    const container = $("#history-matrix-content");
    container.replaceChildren();
    const subjects = data.subjects.filter((item) => item.history.length > 0);
    const dates = [...new Set(subjects.flatMap((item) => item.history.map((point) => dateKey(point.analysis_at))))]
      .filter(Boolean).sort().slice(-18);
    if (!dates.length) { container.append(node("p", "empty-state", "尚无可展示的历史研判。")); return; }
    const table = node("table", "signal-table history-table");
    const head = node("thead"); const headRow = node("tr");
    headRow.append(node("th", "subject-column", "主题"));
    dates.forEach((date) => { const th = node("th", "date-column", date.slice(5).replace("-", "/")); th.title = date; headRow.append(th); });
    head.append(headRow); table.append(head);
    const body = node("tbody");
    subjects.forEach((item) => {
      const row = node("tr");
      const subject = node("th", "subject-column"); subject.scope = "row";
      const link = node("a", "subject-link", item.name); link.href = item.timeline_url; subject.append(link); row.append(subject);
      const byDate = new Map(); item.history.forEach((point) => byDate.set(dateKey(point.analysis_at), point));
      dates.forEach((date) => {
        const cell = node("td", "history-value"); const point = byDate.get(date);
        if (point) cell.append(makeSignalCell(item, point));
        else cell.append(node("span", "history-gap", ""));
        row.append(cell);
      });
      body.append(row);
    });
    table.append(body); container.append(table);
    requestAnimationFrame(() => { container.scrollLeft = container.scrollWidth; });
  }

  function closeDrawer() {
    $("#signal-drawer").hidden = true; $("#drawer-backdrop").hidden = true;
    document.body.classList.remove("drawer-open");
  }

  async function openDrawer(button) {
    const drawer = $("#signal-drawer");
    $("#drawer-title").textContent = `${button.dataset.subject} · ${directionLabel(button.dataset.direction)}`;
    $("#drawer-meta").textContent = formatDate(button.dataset.analysisAt, true);
    $("#drawer-evidence").textContent = button.dataset.evidence || "暂无证据摘要";
    $("#drawer-timeline").href = `/timeline?subject=${encodeURIComponent(button.dataset.subject)}`;
    $("#drawer-content").textContent = "加载中…";
    drawer.hidden = false; $("#drawer-backdrop").hidden = false; document.body.classList.add("drawer-open");
    $("#drawer-close").focus();
    if (!button.dataset.hash) { $("#drawer-content").textContent = "该节点暂无原文索引。"; return; }
    try {
      const response = await fetch(`/api/timeline/report/${encodeURIComponent(button.dataset.hash)}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const report = await response.json();
      const content = report.content || report.summary || "暂无报告原文";
      $("#drawer-content").textContent = content.length > 6000 ? `${content.slice(0, 6000)}\n\n……（摘录已截断）` : content;
    } catch (error) {
      $("#drawer-content").textContent = `原文加载失败：${error.message}`;
    }
  }

  function renderChanges(data) {
    const feed = $("#recent-changes"); feed.replaceChildren();
    if (!data.recent_changes.length) { feed.append(node("p", "empty-state", "现有记录中尚未发现方向切换。")); return; }
    data.recent_changes.forEach((item) => {
      const link = node("a", "change-item"); link.href = item.timeline_url;
      const marker = node("span", `change-marker ${item.to_direction}`);
      const content = node("div", "change-content"); const top = node("div", "change-title");
      top.append(node("strong", "", item.subject), node("time", "", formatDate(item.analysis_at, true)));
      content.append(top, node("p", "change-direction", `${directionLabel(item.from_direction)} → ${directionLabel(item.to_direction)}`), node("p", "change-evidence", item.evidence));
      link.append(marker, content); feed.append(link);
    });
  }

  function renderHealth(data) {
    const health = data.automation_health;
    const rows = [
      [health.errors ? "需要处理" : "自动入库正常", health.errors ? `${health.errors} 次失败` : `${health.publications} 次结构化发布`, health.errors ? "danger" : "success"],
      ["最后自动发布", health.last_published_at ? formatDate(health.last_published_at, true) : "尚无记录", ""],
      ["旧报告整理", `${data.totals.needs_review} 份`, "muted"],
      ["分析工作台", `${data.totals.chat_analyses} 条历史记录`, ""],
    ];
    const container = $("#health-content"); container.replaceChildren();
    rows.forEach(([label, value, tone]) => { const row = node("div", `health-row ${tone}`); row.append(node("span", "", label), node("strong", "", value)); container.append(row); });
    container.append(node("p", "health-note", "旧报告整理属于历史数据治理，不影响新报告自动建立三周期轨道。"));
    const actions = node("div", "health-actions");
    const ask = node("a", "health-action primary", "发起新分析"); ask.href = "/ask";
    const history = node("a", "health-action", "查看全部时间线"); history.href = "/timeline";
    actions.append(ask, history); container.append(actions);
  }

  function render(data) {
    renderMetrics(data); renderHorizons(data); renderHistory(data); renderChanges(data); renderHealth(data);
    $("#load-error").hidden = true;
  }

  async function load() {
    try {
      const response = await fetch("/api/management/summary");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
    } catch (error) { $("#load-error-message").textContent = error.message; $("#load-error").hidden = false; }
  }

  document.addEventListener("click", (event) => { const cell = event.target.closest(".signal-cell"); if (cell) openDrawer(cell); });
  $("#drawer-close").addEventListener("click", closeDrawer); $("#drawer-backdrop").addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeDrawer(); });
  $("#retry").addEventListener("click", load); setupTheme(); load();
})();
