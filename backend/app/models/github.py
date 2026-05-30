"""GitHub PR 相关数据模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class PRRef(BaseModel):
    """从 PR URL 解析出的定位信息。"""

    owner: str
    repo: str
    number: int

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    def __str__(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


class PRFile(BaseModel):
    """PR 中单个变更文件。"""

    filename: str
    status: str  # added / modified / removed / renamed
    additions: int = 0
    deletions: int = 0
    changes: int = 0
    # GitHub 返回的该文件 unified diff 片段（二进制文件可能为空）
    patch: str | None = None
    previous_filename: str | None = None


class PRCommit(BaseModel):
    """PR 中的单个提交。"""

    sha: str
    message: str
    author: str | None = None
    date: str | None = None


class FileContext(BaseModel):
    """某个文件在指定 ref 下的完整内容（用于补充跨文件上下文）。"""

    filename: str
    content: str


class PullRequest(BaseModel):
    """一个 PR 的完整抓取结果。"""

    ref: PRRef
    title: str
    body: str | None = None
    author: str | None = None
    state: str
    base_branch: str
    head_branch: str
    base_sha: str
    head_sha: str
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    html_url: str = ""
    files: list[PRFile] = Field(default_factory=list)
    commits: list[PRCommit] = Field(default_factory=list)
