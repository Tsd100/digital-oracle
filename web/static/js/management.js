(() => {
  "use strict";

  const directionLabels = {
    strong_bullish: "强势偏多", bullish: "偏多", neutral: "震荡或修复",
    mixed: "短中期分歧", bearish: "偏空", strong_bearish: "强势偏空",
    not_applicable: "不适用", unknown: "尚未判定",
  };
  const horizonLabels = { short: "短期", swing: "波段", medium: "中期" };
  let dashboardData = null;
  let activeFilter = "all";

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

  function subjectVisible(item) {
    if (activeFilter === "changed") return Boolean(item.previous_direction);
    if (activeFilter === "current") return item.freshness === "current";
    return item.report_count > 0;
  }

  function renderSubjects(data) {
    const grid = $("#subject-grid");
    grid.replaceChildren();
    const items = data.subjects.filter(subjectVisible);
    items.forEach((item) => {
      const link = node("a", `subject-card ${item.latest_direction} freshness-${item.freshness}`);
      link.href = item.timeline_url;
      link.dataset.changed = item.previous_direction ? "true" : "false";
      const head = node("div", "subject-head");
      const title = node("div", "");
      title.append(node("h3", "", item.name));
      title.append(node("span", "subject-time", formatDate(item.latest_analysis_at, true)));
      head.append(title);
      head.append(node("span", `direction-badge ${item.latest_direction}`, directionLabel(item.latest_direction)));
      link.append(head);
      link.append(node("p", "subject-evidence", item.latest_evidence));

      if (item.previous_direction) {
        const change = node("p", "subject-change");
        change.append(node("span", "", "最近变化"));
        change.append(document.createTextNode(`${directionLabel(item.previous_direction)} → ${directionLabel(item.latest_direction)}`));
        link.append(change);
      } else {
        link.append(node("p", "subject-change stable", "现有记录中暂无方向切换"));
      }

      const horizons = node("div", "horizon-row");
      if (item.horizons.length) {
        item.horizons.forEach((trend) => {
          const chip = node("span", `horizon-chip ${trend.direction}`);
          chip.append(node("b", "", horizonLabels[trend.horizon] || trend.horizon));
          chip.append(document.createTextNode(directionLabel(trend.direction)));
          horizons.append(chip);
        });
      } else {
        horizons.append(node("span", "horizon-chip legacy", "历史报告轨道"));
      }
      link.append(horizons);
      const footer = node("div", "subject-footer");
      footer.append(node("span", "", `${item.report_count} 份报告 · ${item.resolved_count} 个有效节点`));
      footer.append(node("span", "open-label", "查看时间线 →"));
      link.append(footer);
      grid.append(link);
    });
    if (!items.length) grid.append(node("p", "empty-state", "当前筛选下没有主题。"));
  }

  function renderChanges(data) {
    const feed = $("#recent-changes");
    feed.replaceChildren();
    if (!data.recent_changes.length) {
      feed.append(node("p", "empty-state", "现有记录中尚未发现方向切换。"));
      return;
    }
    data.recent_changes.forEach((item) => {
      const link = node("a", "change-item");
      link.href = item.timeline_url;
      const marker = node("span", `change-marker ${item.to_direction}`);
      const content = node("div", "change-content");
      const top = node("div", "change-title");
      top.append(node("strong", "", item.subject));
      top.append(node("time", "", formatDate(item.analysis_at, true)));
      content.append(top);
      content.append(node("p", "change-direction", `${directionLabel(item.from_direction)} → ${directionLabel(item.to_direction)}`));
      content.append(node("p", "change-evidence", item.evidence));
      link.append(marker, content);
      feed.append(link);
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
    const container = $("#health-content");
    container.replaceChildren();
    rows.forEach(([label, value, tone]) => {
      const row = node("div", `health-row ${tone}`);
      row.append(node("span", "", label), node("strong", "", value));
      container.append(row);
    });
    const note = node("p", "health-note", "旧报告整理属于历史数据治理，不影响新报告自动建立三周期轨道。");
    container.append(note);
    const actions = node("div", "health-actions");
    const ask = node("a", "health-action primary", "发起新分析"); ask.href = "/ask";
    const history = node("a", "health-action", "查看全部时间线"); history.href = "/timeline";
    actions.append(ask, history); container.append(actions);
  }

  function render(data) {
    dashboardData = data;
    renderMetrics(data); renderSubjects(data); renderChanges(data); renderHealth(data);
    $("#load-error").hidden = true;
  }

  async function load() {
    try {
      const response = await fetch("/api/management/summary");
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      render(await response.json());
    } catch (error) {
      $("#load-error-message").textContent = error.message;
      $("#load-error").hidden = false;
    }
  }

  document.querySelectorAll(".filter").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.toggle("active", item === button));
    activeFilter = button.dataset.filter;
    if (dashboardData) renderSubjects(dashboardData);
  }));
  $("#retry").addEventListener("click", load);
  setupTheme(); load();
})();
