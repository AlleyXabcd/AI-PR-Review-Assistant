"""流式分析编排：并发跑 summary / risks，按完成顺序产出事件。

事件序列：stage（进度提示）→ summary / risks（谁先分析完谁先到）→ done。
任一分析抛错则产出 error 事件并取消其余任务后结束。

产出的是与 SSE 无关的结构化 StreamEvent，由路由层用 format_sse 转成 text/event-stream，
便于编排逻辑独立于传输格式测试。
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.models.github import PRRef
from app.services.cache import AnalysisCache
from app.services.deepseek_client import DeepSeekError
from app.services.github_client import GitHubError
from app.services.risk_service import RiskService
from app.services.summary_service import SummaryService

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """一条流式事件：event 为 SSE 事件名，data 为可 JSON 序列化的负载。"""

    event: str
    data: dict = field(default_factory=dict)


def format_sse(event: StreamEvent) -> str:
    """把 StreamEvent 渲染为 SSE 帧。

    json.dumps 默认会转义换行，单行 data 不会破坏 SSE 分帧。
    """
    payload = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.event}\ndata: {payload}\n\n"


def _error_message(exc: Exception) -> str:
    if isinstance(exc, GitHubError):
        return f"GitHub 抓取失败：{exc}"
    if isinstance(exc, DeepSeekError):
        return f"模型调用失败：{exc}"
    return f"分析失败：{exc}"


async def stream_analysis(
    ref: PRRef,
    *,
    summary_service: SummaryService | None = None,
    risk_service: RiskService | None = None,
    cache: AnalysisCache | None = None,
) -> AsyncIterator[StreamEvent]:
    """流式执行分析：先逐字产出总结概述正文，再产出风险识别结果。

    事件序列：stage → summary_delta*（逐 token）→ summary（完整结构化）
    → risks → done。任一步出错产出 error 后结束。
    """
    summary_service = summary_service or SummaryService(cache=cache)
    risk_service = risk_service or RiskService(cache=cache)

    yield StreamEvent("stage", {"message": "正在抓取 PR 并生成变更总结…"})

    # 风险识别与总结并发启动；总结边流式边产出，风险整块在其后到达
    risk_task = asyncio.ensure_future(risk_service.detect(ref))
    try:
        try:
            async for chunk in summary_service.summarize_stream(ref):
                if chunk.delta:
                    yield StreamEvent("summary_delta", {"text": chunk.delta})
                if chunk.result is not None:
                    yield StreamEvent("summary", chunk.result.model_dump())
        except (GitHubError, DeepSeekError) as exc:
            logger.warning("流式总结失败：%s", exc)
            yield StreamEvent("error", {"message": _error_message(exc)})
            return

        yield StreamEvent("stage", {"message": "正在识别风险代码…"})
        try:
            risks = await risk_task
        except (GitHubError, DeepSeekError) as exc:
            logger.warning("流式风险识别失败：%s", exc)
            yield StreamEvent("error", {"message": _error_message(exc)})
            return
        yield StreamEvent("risks", risks.model_dump())
    finally:
        if not risk_task.done():
            risk_task.cancel()
            await asyncio.gather(risk_task, return_exceptions=True)

    yield StreamEvent("done", {})
