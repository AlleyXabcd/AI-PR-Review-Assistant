"""从 LLM 文本输出中稳健地解析 JSON。

模型有时会用 ```json 包裹，或在 JSON 前后带少量说明文字，这里做容错提取。
"""
from __future__ import annotations

import json
import re

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict:
    """尽力从文本中提取首个 JSON 对象，失败时抛 ValueError。"""
    if not text or not text.strip():
        raise ValueError("模型返回为空")

    candidate = text.strip()

    # 1) 去除 markdown 代码块包裹
    fence = _FENCE_RE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()

    # 2) 直接尝试
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # 3) 截取首个 { 到末个 } 之间的内容再试
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = candidate[start : end + 1]
        try:
            return json.loads(snippet)
        except json.JSONDecodeError as exc:
            raise ValueError(f"无法解析模型返回的 JSON：{exc}") from exc

    raise ValueError("模型返回中未找到 JSON 对象")
