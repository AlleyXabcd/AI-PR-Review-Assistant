"""Review（变更总结、风险识别等）相关数据模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.github import PRCommit, PRFile
from app.models.llm import TokenUsage

# 风险严重级别与分类的合法取值（也用于服务层归一化模型输出）
Severity = Literal["high", "medium", "low"]
Category = Literal["security", "performance", "correctness", "maintainability"]

SEVERITIES: tuple[str, ...] = ("high", "medium", "low")
CATEGORIES: tuple[str, ...] = (
    "security",
    "performance",
    "correctness",
    "maintainability",
)


class SummaryRequest(BaseModel):
    """变更总结请求。"""

    pr_url: str = Field(..., description="GitHub PR 地址或 owner/repo#number 简写")


class RiskRequest(BaseModel):
    """风险识别请求。"""

    pr_url: str = Field(..., description="GitHub PR 地址或 owner/repo#number 简写")


class WritebackRequest(BaseModel):
    """评论回写请求。

    dry_run=True（默认）只返回将要发送的评论预览，不调用 GitHub 写接口；
    前端确认后再以 dry_run=False 真正发送。
    """

    pr_url: str = Field(..., description="GitHub PR 地址或 owner/repo#number 简写")
    dry_run: bool = Field(True, description="为 True 时只预览不发送")


class WritebackResponse(BaseModel):
    """评论回写响应。"""

    posted: bool = Field(False, description="是否已真正发送到 GitHub")
    dry_run: bool = Field(True, description="本次是否为预览模式")
    body: str = Field("", description="评论 Markdown 正文（预览或已发送内容）")
    comment_url: str = Field("", description="已发送评论的 API/页面地址，预览时为空")
    model: str = Field("", description="生成分析所用模型")



class FileChange(BaseModel):
    """返回给前端的文件变更信息（含 unified diff 片段，供前端高亮）。"""

    filename: str
    status: str
    additions: int = 0
    deletions: int = 0
    # GitHub 返回的该文件 unified diff 片段（二进制/超大文件可能为空）
    patch: str | None = None


class PRSummary(BaseModel):
    """LLM 产出的结构化变更总结。"""

    overview: str = Field(..., description="一段话概述本次 PR 的意图与改动")
    key_changes: list[str] = Field(
        default_factory=list, description="关键改动要点列表"
    )
    impact: str = Field("", description="潜在影响与需要关注的点")


class SummaryResponse(BaseModel):
    """变更总结接口的完整响应。"""

    # PR 基础元信息
    title: str
    author: str | None = None
    state: str
    base_branch: str
    head_branch: str
    html_url: str = ""
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0

    files: list[FileChange] = Field(default_factory=list)
    commits: list[PRCommit] = Field(default_factory=list)

    summary: PRSummary
    model: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    # 命中缓存时为 True（不重新调用模型，直接返回历史分析结果）
    cached: bool = False


class RiskItem(BaseModel):
    """单条风险点。"""

    file: str = Field(..., description="风险所在文件路径")
    line: int | None = Field(None, description="风险所在行号（diff 新文件行号，可空）")
    severity: Severity = Field("low", description="严重级别")
    category: Category = Field("correctness", description="风险分类")
    title: str = Field(..., description="一句话风险标题")
    detail: str = Field("", description="风险说明：为什么这是个问题")
    suggestion: str = Field("", description="可执行的修改建议")
    confidence: float = Field(
        0.5, ge=0.0, le=1.0, description="模型对该风险的置信度 0~1"
    )


class RisksResponse(BaseModel):
    """风险识别接口的完整响应。"""

    # PR 基础元信息
    title: str
    author: str | None = None
    state: str
    base_branch: str
    head_branch: str
    html_url: str = ""
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0

    files: list[FileChange] = Field(default_factory=list)

    risks: list[RiskItem] = Field(default_factory=list)
    model: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    # 命中缓存时为 True（不重新调用模型，直接返回历史分析结果）
    cached: bool = False


def to_file_changes(files: list[PRFile]) -> list[FileChange]:
    return [
        FileChange(
            filename=f.filename,
            status=f.status,
            additions=f.additions,
            deletions=f.deletions,
            patch=f.patch,
        )
        for f in files
    ]
