/* Digital Oracle Web Dashboard — Frontend Logic */
(function () {
  "use strict";

  // ---- State ----
  let activeId = null;
  let eventSource = null;
  let reportText = "";

  // ---- DOM refs ----
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const sidebar = $("#sidebar");
  const historyList = $("#history-list");
  const emptyHistory = $("#empty-history");
  const mainContent = $("#main-content");
  const questionForm = $("#question-form");
  const questionInput = $("#question-input");
  const askBtn = $("#ask-btn");
  const workflowPanel = $("#workflow-panel");
  const step1Icon = $("#step1-icon");
  const step2Icon = $("#step2-icon");
  const step3Icon = $("#step3-icon");
  const step1Detail = $("#step1-detail");
  const step2Detail = $("#step2-detail");
  const step3Detail = $("#step3-detail");
  const providerMiniList = $("#provider-mini-list");
  const reportArea = $("#report-area");
  const reportContent = $("#report-content");
  const reportActions = $("#report-actions");
  const newQuestionBtn = $("#new-question-btn");
  const downloadBtn = $("#download-btn");
  const toggleSidebarBtn = $("#toggle-sidebar");
  const modelSelect = $("#model-select");

  // ---- Sidebar toggle ----
  toggleSidebarBtn.addEventListener("click", () => {
    sidebar.classList.toggle("collapsed");
  });

  // ---- History ----
  async function loadHistory() {
    try {
      const res = await fetch("/api/history");
      const items = await res.json();
      historyList.innerHTML = "";

      if (items.length === 0) {
        emptyHistory.style.display = "block";
        return;
      }
      emptyHistory.style.display = "none";

      items.forEach((item) => {
        const div = document.createElement("div");
        div.className = "history-item" + (item.id === activeId ? " active" : "");
        div.innerHTML = `
          <div class="q-text">${escHtml(item.question)}</div>
          <div class="q-meta">
            <span class="status-dot ${item.status}"></span>
            <span>${item.status}</span>
            <span>${fmtDate(item.created_at)}</span>
          </div>
          <button class="delete-btn" data-id="${item.id}" title="Delete">&times;</button>
        `;
        div.addEventListener("click", (e) => {
          if (e.target.classList.contains("delete-btn")) return;
          loadHistoryItem(item.id);
        });
        div.querySelector(".delete-btn").addEventListener("click", (e) => {
          e.stopPropagation();
          deleteItem(item.id);
        });
        historyList.appendChild(div);
      });
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  }

  async function loadHistoryItem(id) {
    try {
      const res = await fetch(`/api/history/${id}`);
      const item = await res.json();
      if (!item || !item.report) return;

      activeId = item.id;
      resetUI();
      questionInput.value = item.question;
      reportContent.innerHTML = renderMarkdown(item.report);
      reportArea.classList.add("visible");
      reportActions.style.display = "flex";
      reportText = item.report;

      highlightSidebarActive();
    } catch (err) {
      console.error("Failed to load history item:", err);
    }
  }

  async function deleteItem(id) {
    if (!confirm("Delete this question and report?")) return;
    try {
      await fetch(`/api/history/${id}`, { method: "DELETE" });
      if (activeId === id) {
        activeId = null;
      }
      loadHistory();
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  }

  function highlightSidebarActive() {
    $$(".history-item").forEach((el) => {
      el.classList.toggle("active", el.querySelector(".delete-btn")?.dataset.id === activeId);
    });
  }

  // ---- Question submission ----
  questionForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const question = questionInput.value.trim();
    if (!question) return;

    // UI: reset for new analysis
    resetUI();
    workflowPanel.classList.add("visible");
    askBtn.disabled = true;
    askBtn.textContent = "分析中...";
    reportText = "";

    // Step icons
    step1Icon.className = "step-icon active";
    step1Icon.textContent = "1";
    step2Icon.className = "step-icon";
    step2Icon.textContent = "2";
    step3Icon.className = "step-icon";
    step3Icon.textContent = "3";
    step1Detail.textContent = "理解问题并选择数据源...";

    // POST question
    try {
      const res = await fetch("/api/question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, model: modelSelect.value }),
      });
      const data = await res.json();
      if (data.error) {
        showError(data.error);
        return;
      }
      activeId = data.id;
      connectSSE(data.id);
      loadHistory();
    } catch (err) {
      showError("请求失败: " + err.message);
    }
  });

  // ---- SSE connection ----
  function connectSSE(id) {
    if (eventSource) eventSource.close();

    eventSource = new EventSource(`/api/question/${id}/stream`);

    eventSource.addEventListener("progress", (e) => {
      const data = JSON.parse(e.data);
      handleProgress(data);
    });

    eventSource.addEventListener("chunk", (e) => {
      const data = JSON.parse(e.data);
      reportText += data.text;
      reportContent.innerHTML = renderMarkdown(reportText);
      reportArea.classList.add("visible");
      // Auto-scroll
      reportContent.scrollIntoView({ behavior: "smooth", block: "end" });
    });

    eventSource.addEventListener("done", (e) => {
      const data = JSON.parse(e.data);
      finishAnalysis(data);
    });

    eventSource.addEventListener("error", (e) => {
      let message = "分析过程中出现错误";
      try {
        const data = JSON.parse(e.data);
        message = data.message || message;
      } catch (_) {}
      showError(message);
    });
  }

  // ---- Progress handler ----
  function handleProgress(data) {
    if (data.step === 1) {
      step1Icon.className = "step-icon done";
      step1Icon.textContent = "✓";
      step1Detail.textContent = data.message + " (" + (data.provider_count || "?") + " 个数据源)";
      step2Icon.className = "step-icon active";
      step2Icon.textContent = "2";
      step2Detail.textContent = "并行拉取数据中...";
      // Build provider mini badges
      providerMiniList.innerHTML = "";
      const labels = data.provider_labels || [];
      labels.forEach((label) => {
        const span = document.createElement("span");
        span.className = "provider-mini";
        span.textContent = label;
        span.dataset.label = label;
        providerMiniList.appendChild(span);
      });
    }

    if (data.step === 2 && data.provider) {
      const mini = providerMiniList.querySelector(`[data-label="${data.provider}"]`);
      if (mini) {
        mini.className = "provider-mini " + data.status;
      }
      if (data.status === "done" || data.status === "error") {
        step2Detail.textContent = data.status === "error"
          ? `数据拉取完成 (部分失败: ${data.error})`
          : "数据拉取完成";
      }
    }

    if (data.step === 2 && data.provider === undefined) {
      // Step 2 starting
    }

    if (data.step === 3) {
      step2Icon.className = "step-icon done";
      step2Icon.textContent = "✓";
      step3Icon.className = "step-icon active";
      step3Icon.textContent = "3";
      step3Detail.textContent = data.message;
    }
  }

  function finishAnalysis(data) {
    step1Icon.className = "step-icon done";
    step1Icon.textContent = "✓";
    step2Icon.className = "step-icon done";
    step2Icon.textContent = "✓";
    step3Icon.className = "step-icon done";
    step3Icon.textContent = "✓";
    step3Detail.textContent = data.llm_used
      ? "AI 分析报告生成完毕"
      : "原始数据报告生成完毕 (配置 DEEPSEEK_API_KEY 获取 AI 分析)";

    askBtn.disabled = false;
    askBtn.textContent = "提问";
    reportActions.style.display = "flex";

    if (eventSource) eventSource.close();
    loadHistory();

    if (!reportText) {
      reportContent.innerHTML = renderMarkdown("*报告为空*");
      reportArea.classList.add("visible");
    }
  }

  function showError(message) {
    step1Icon.className = "step-icon" + (step1Icon.textContent === "✓" ? " done" : " error");
    step2Icon.className = "step-icon" + (step2Icon.textContent === "✓" ? " done" : " error");
    step3Icon.className = "step-icon error";
    step3Icon.textContent = "!";
    step3Detail.textContent = "错误: " + message;

    askBtn.disabled = false;
    askBtn.textContent = "提问";
    reportContent.innerHTML = renderMarkdown("### 分析失败\n\n" + message);
    reportArea.classList.add("visible");
    reportActions.style.display = "flex";

    if (eventSource) eventSource.close();
  }

  // ---- Markdown rendering ----
  function renderMarkdown(text) {
    if (typeof marked === "undefined") {
      return `<pre>${escHtml(text)}</pre>`;
    }
    try {
      return marked.parse(text);
    } catch (_) {
      return `<pre>${escHtml(text)}</pre>`;
    }
  }

  // ---- Download ----
  downloadBtn.addEventListener("click", () => {
    if (!activeId) return;
    window.open(`/api/question/${activeId}/download`, "_blank");
  });

  newQuestionBtn.addEventListener("click", () => {
    activeId = null;
    resetUI();
    questionInput.value = "";
    questionInput.focus();
  });

  // ---- Helpers ----
  function resetUI() {
    workflowPanel.classList.remove("visible");
    reportArea.classList.remove("visible");
    reportActions.style.display = "none";
    reportText = "";
    reportContent.innerHTML = "";
    askBtn.disabled = false;
    askBtn.textContent = "提问";
    step1Icon.className = "step-icon";
    step1Icon.textContent = "1";
    step2Icon.className = "step-icon";
    step2Icon.textContent = "2";
    step3Icon.className = "step-icon";
    step3Icon.textContent = "3";
    step1Detail.textContent = "";
    step2Detail.textContent = "";
    step3Detail.textContent = "";
    providerMiniList.innerHTML = "";
    if (eventSource) { eventSource.close(); eventSource = null; }
  }

  function escHtml(s) {
    const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return String(s).replace(/[&<>"']/g, (c) => map[c]);
  }

  function fmtDate(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 60 * 60 * 1000) return Math.floor(diff / 60000) + "m ago";
    if (diff < 24 * 60 * 60 * 1000) return Math.floor(diff / 3600000) + "h ago";
    return d.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  }

  // ---- Init ----
  loadHistory();
  questionInput.focus();
})();
