"""Report generation — raw data fallback and DeepSeek LLM integration."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from queue import Queue
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = PROJECT_ROOT / "SKILL.md"

# Load SKILL.md content once at module level
_SKILL_CONTENT: str | None = None


def _get_skill_content() -> str:
    global _SKILL_CONTENT
    if _SKILL_CONTENT is None:
        try:
            _SKILL_CONTENT = SKILL_PATH.read_text(encoding="utf-8")
        except Exception:
            _SKILL_CONTENT = ""
    return _SKILL_CONTENT


# ---------------------------------------------------------------------------
# DeepSeek configuration
# ---------------------------------------------------------------------------

AVAILABLE_MODELS = ("deepseek-v4-pro", "deepseek-v4-flash")
DEFAULT_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")


def _api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY")


def _base_url() -> str:
    return os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")


def _is_llm_configured() -> bool:
    return bool(_api_key())


# ---------------------------------------------------------------------------
# Raw data report (no LLM)
# ---------------------------------------------------------------------------

def _generate_raw_report(question: str, results: dict[str, Any]) -> str:
    lines = [
        f"# {question}",
        "",
        "## 拉取的原始数据",
        "",
        "*以下数据由 Digital Oracle 各 provider 拉取。配置 `DEEPSEEK_API_KEY` 环境变量可获得 AI 分析报告。*",
        "",
    ]

    for label, data in results.get("results", {}).items():
        lines.append(f"### {label}")
        lines.append("")
        if isinstance(data, dict) and "error" in data:
            lines.append(f"*拉取失败: {data['error']}*")
        else:
            lines.append("```json")
            lines.append(json.dumps(data, ensure_ascii=False, indent=2, default=str)[:3000])
            lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append(f"*数据源数量: {len(results.get('provider_labels', []))}*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM report (DeepSeek, streaming)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一个金融数据分析专家。你的任务是基于真实交易市场数据回答用户的问题。

## 核心方法论（来自 SKILL.md）

1. **只用交易数据** — 价格、成交量、持仓量、利差、溢价。不引用新闻、分析文章、或他人观点。
2. **显式推理** — 从价格数据推导出判断，解释"为什么这个价格回答这个问题"。
3. **多信号交叉验证** — 至少 3 个独立维度，单一信号不能下结论。
4. **标注时间窗口** — 期权定价 3 个月、设备订单定价 3 年——不同期限的信号不能混投。
5. **结构化输出** — 严格按以下模板输出报告。

## 输出模板

```markdown
# [问题标题]: 多信号综合研判

## 一、数据概览

### Layer 1: [最直接信号源]
| 信号 | 数据 | 信号解读 |
|------|------|----------|
(table)

### Layer 2: [次级信号源]
(same)

### Layer N: ...

## 二、分析

### 共振信号
### 关键矛盾
### 时间分层

## 三、概率估计
| 场景 | 概率 | 依据 |

### 最可能路径

## 四、结论
> 一句话总结

### 分维度结论
| 维度 | 判断 | 置信度 |

### 建议关注的信号
| 信号 | 当前值 | 阈值 | 含义 |
```

## 机器可读趋势数据（市场走势问题必须输出）

在报告正文末尾附加且只附加一个 `do-trend` 代码块，代码块起始标记必须是 ```do-trend。JSON 至少包含：

```json
{
  "schema_version": "1.0",
  "analysis_id": "稳定且唯一的分析编号",
  "analysis_at": "带时区的 ISO 时间",
  "data_as_of": "带时区的数据截止时间",
  "subjects": [{
    "subject_id": "稳定英文标识",
    "subject_name": "中文名称",
    "instrument": "标的或合约",
    "quote_currency": "计价币种",
    "quote_unit": "计价单位",
    "horizons": {
      "short": {"direction": "bullish", "confidence": 65, "summary": "短线结论"}
    }
  }]
}
```

周期只使用 `short`（1～5 个交易日）、`swing`（1～4 周）、`medium`（1～3 个月），未分析的周期直接省略。方向只使用 `strong_bullish`、`bullish`、`neutral`、`bearish`、`strong_bearish`、`insufficient`。置信度必须是 0～100 的整数。不要根据没有证据的数据补齐周期。

用中文回答。数据中的 `$` 符号用 `USD` 替代以避免 markdown 渲染问题。"""


def _build_llm_prompt(question: str, results: dict[str, Any]) -> list[dict]:
    data_json = json.dumps(results.get("results", {}), ensure_ascii=False, indent=2, default=str)
    # Limit data size
    if len(data_json) > 80000:
        data_json = data_json[:80000]

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"## 用户问题\n\n{question}\n\n## 拉取的交易数据\n\n```json\n{data_json}\n```\n\n请基于以上真实交易数据，按照方法论分析并回答用户的问题。严格遵循输出模板格式。"},
    ]


def generate_llm_report(question: str, results: dict[str, Any], queue: Queue, model: str = DEFAULT_MODEL) -> str:
    api_key = _api_key()
    base_url = _base_url()

    messages = _build_llm_prompt(question, results)

    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 6000,
        "temperature": 0.3,
    }).encode("utf-8")

    url = f"{base_url.rstrip('/')}/chat/completions"
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "text/event-stream")

    full_text = ""

    try:
        with urlopen(req, timeout=180) as resp:
            for line in resp:
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str.startswith("data: "):
                    continue
                data_str = line_str[6:]
                if data_str == "[DONE]":
                    break

                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_text += content
                        queue.put({"event": "chunk", "data": {"text": content}})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
    except URLError as exc:
        queue.put({"event": "error", "data": {"message": f"DeepSeek API 请求失败: {exc}"}})
        if full_text:
            queue.put({"event": "chunk", "data": {"text": "\n\n---\n*[报告不完整 — API 连接中断]*"}})
        return full_text if full_text else ""
    except Exception as exc:
        queue.put({"event": "error", "data": {"message": f"报告生成异常: {exc}"}})
        return full_text if full_text else ""

    return full_text


def generate_report(question: str, results: dict[str, Any], queue: Queue, model: str = DEFAULT_MODEL) -> str:
    if _is_llm_configured():
        queue.put({"event": "progress", "data": {"step": 3, "message": f"DeepSeek ({model}) 正在生成分析报告..."}})
        report = generate_llm_report(question, results, queue, model=model)
        if not report:
            report = _generate_raw_report(question, results)
        return report

    queue.put({"event": "progress", "data": {"step": 3, "message": "生成原始数据报告 (设置 DEEPSEEK_API_KEY 获取 AI 分析)"}})
    return _generate_raw_report(question, results)
