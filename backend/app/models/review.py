"""Review（变更总结等）相关数据模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.github import PRCommit, PRFile
from app.models.llm import TokenUsage


class SummaryRequest(BaseModel):
    """变更总结请求。"""

    pr_url: str = Field(..., description="GitHub PR 地址或 owner/repo#number 简写")


class FileChange(BaseModel):
    """返回给前端的精简文件变更信息（不含 diff 正文）。"""

    filename: str
    status: str
    additions: int = 0
    deletions: int = 0


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


def to_file_changes(files: list[PRFile]) -> list[FileChange]:
    return [
        FileChange(
            filename=f.filename,
            status=f.status,
            additions=f.additions,
            deletions=f.deletions,
        )
        for f in files
    ]
