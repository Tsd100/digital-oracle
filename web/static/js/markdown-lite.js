(() => {
  "use strict";

  function escapeHtml(value) {
    return value.replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[char]);
  }

  function inline(value) {
    return value
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }

  function parse(markdown) {
    const safe = escapeHtml(String(markdown || "")).replace(/\r\n/g, "\n");
    const blocks = [];
    const protectedText = safe.replace(/```(?:[^\n]*)\n([\s\S]*?)```/g, (_, code) => {
      blocks.push(`<pre><code>${code.trimEnd()}</code></pre>`);
      return `\n@@DO_BLOCK_${blocks.length - 1}@@\n`;
    });
    const output = protectedText.split(/\n{2,}/).map((block) => {
      const value = block.trim();
      if (!value) return "";
      const token = value.match(/^@@DO_BLOCK_(\d+)@@$/);
      if (token) return blocks[Number(token[1])];
      const heading = value.match(/^(#{1,4})\s+(.+)$/s);
      if (heading) {
        const level = heading[1].length;
        return `<h${level}>${inline(heading[2].replace(/\n/g, " "))}</h${level}>`;
      }
      const lines = value.split("\n");
      if (lines.every((line) => /^[-*]\s+/.test(line))) {
        return `<ul>${lines.map((line) => `<li>${inline(line.replace(/^[-*]\s+/, ""))}</li>`).join("")}</ul>`;
      }
      return `<p>${inline(value).replace(/\n/g, "<br>")}</p>`;
    }).join("\n");
    return output;
  }

  window.marked = { parse };
})();
