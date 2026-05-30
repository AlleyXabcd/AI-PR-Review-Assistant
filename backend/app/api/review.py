"""Review 相关路由。"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.review import (
    RiskRequest,
    RisksResponse,
    SummaryRequest,
    SummaryResponse,
    WritebackRequest,
    WritebackResponse,
)
from app.services.cache import get_cache
from app.services.deepseek_client import DeepSeekError
from app.services.github_client import GitHubError, parse_pr_url
from app.services.review_stream import StreamEvent, format_sse, stream_analysis
from app.services.risk_service import RiskService
from app.services.summary_service import SummaryService
from app.services.writeback_service import WritebackService

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/summary", response_model=SummaryResponse)
async def create_summary(req: SummaryRequest) -> SummaryResponse:
    """抓取指定 PR 并生成结构化变更总结。"""
    try:
        ref = parse_pr_url(req.pr_url)
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = SummaryService(cache=get_cache())
    try:
        return await service.summarize(ref)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub 抓取失败：{exc}") from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc


@router.post("/risks", response_model=RisksResponse)
async def detect_risks(req: RiskRequest) -> RisksResponse:
    """抓取指定 PR 并识别其中的风险代码。"""
    try:
        ref = parse_pr_url(req.pr_url)
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = RiskService(cache=get_cache())
    try:
        return await service.detect(ref)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub 抓取失败：{exc}") from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc


@router.post("/writeback", response_model=WritebackResponse)
async def writeback(req: WritebackRequest) -> WritebackResponse:
    """把分析结果拼成评论回写到 GitHub PR。

    dry_run=True（默认）只返回评论预览不发送；dry_run=False 才真正发布，
    需要 GITHUB_TOKEN 对目标仓库具备写权限。
    """
    try:
        ref = parse_pr_url(req.pr_url)
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = WritebackService(cache=get_cache())
    try:
        return await service.build(ref, dry_run=req.dry_run)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub 操作失败：{exc}") from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc


@router.get("/stream")
async def stream_review(pr_url: str) -> StreamingResponse:
    """以 SSE 流式返回分析进度与结果：summary / risks 谁先分析完谁先到。

    用浏览器原生 EventSource 消费（GET + text/event-stream）。
    """

    async def event_source() -> AsyncIterator[str]:
        try:
            ref = parse_pr_url(pr_url)
        except GitHubError as exc:
            yield format_sse(StreamEvent("error", {"message": str(exc)}))
            return
        async for event in stream_analysis(ref, cache=get_cache()):
            yield format_sse(event)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
