"""Review 相关路由。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.review import (
    RiskRequest,
    RisksResponse,
    SummaryRequest,
    SummaryResponse,
)
from app.services.deepseek_client import DeepSeekError
from app.services.github_client import GitHubError, parse_pr_url
from app.services.risk_service import RiskService
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/review", tags=["review"])


@router.post("/summary", response_model=SummaryResponse)
async def create_summary(req: SummaryRequest) -> SummaryResponse:
    """抓取指定 PR 并生成结构化变更总结。"""
    try:
        ref = parse_pr_url(req.pr_url)
    except GitHubError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    service = SummaryService()
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

    service = RiskService()
    try:
        return await service.detect(ref)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub 抓取失败：{exc}") from exc
    except DeepSeekError as exc:
        raise HTTPException(status_code=502, detail=f"模型调用失败：{exc}") from exc
