"""GitHub PR 抓取服务。

职责：
- 解析多种形式的 PR URL / 简写为 PRRef
- 通过 GitHub REST API 拉取 PR 元信息、变更文件、提交列表
"""
from __future__ import annotations

import re

import httpx

from app.core.config import Settings, get_settings
from app.models.github import PRCommit, PRFile, PRRef, PullRequest

# 支持的形式：
#   https://github.com/owner/repo/pull/123
#   github.com/owner/repo/pull/123
#   owner/repo#123
#   owner/repo/pull/123
_URL_RE = re.compile(
    r"github\.com[/:](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+)/pull/(?P<number>\d+)",
    re.IGNORECASE,
)
_SHORT_RE = re.compile(
    r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)(?:#|/pull/)(?P<number>\d+)$"
)


class GitHubError(RuntimeError):
    """GitHub 抓取相关错误。"""


def parse_pr_url(value: str) -> PRRef:
    """把用户输入解析为 PRRef，无法解析时抛 GitHubError。"""
    text = value.strip()
    if not text:
        raise GitHubError("PR 地址不能为空")

    match = _URL_RE.search(text) or _SHORT_RE.match(text)
    if not match:
        raise GitHubError(
            f"无法解析 PR 地址：{value!r}。"
            "支持形如 https://github.com/owner/repo/pull/123 或 owner/repo#123"
        )

    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]

    return PRRef(
        owner=match.group("owner"),
        repo=repo,
        number=int(match.group("number")),
    )


class GitHubClient:
    """对 GitHub REST API 的薄封装。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-pr-review-assistant",
        }
        if self._settings.github_token:
            headers["Authorization"] = f"Bearer {self._settings.github_token}"
        return headers

    async def fetch_pull_request(self, ref: PRRef) -> PullRequest:
        """拉取 PR 元信息 + 变更文件 + 提交，组装为 PullRequest。"""
        base = self._settings.github_api_base.rstrip("/")
        pr_path = f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}"

        async with httpx.AsyncClient(
            base_url=base,
            headers=self._headers(),
            timeout=self._settings.http_timeout,
        ) as client:
            pr_resp = await self._get(client, pr_path)
            pr_json = pr_resp.json()

            files = await self._fetch_files(client, pr_path)
            commits = await self._fetch_commits(client, pr_path)

        return PullRequest(
            ref=ref,
            title=pr_json.get("title", ""),
            body=pr_json.get("body"),
            author=(pr_json.get("user") or {}).get("login"),
            state=pr_json.get("state", "unknown"),
            base_branch=(pr_json.get("base") or {}).get("ref", ""),
            head_branch=(pr_json.get("head") or {}).get("ref", ""),
            base_sha=(pr_json.get("base") or {}).get("sha", ""),
            head_sha=(pr_json.get("head") or {}).get("sha", ""),
            additions=pr_json.get("additions", 0),
            deletions=pr_json.get("deletions", 0),
            changed_files=pr_json.get("changed_files", 0),
            html_url=pr_json.get("html_url", ""),
            files=files,
            commits=commits,
        )

    async def _fetch_files(
        self, client: httpx.AsyncClient, pr_path: str
    ) -> list[PRFile]:
        files: list[PRFile] = []
        async for item in self._paginate(client, f"{pr_path}/files"):
            files.append(
                PRFile(
                    filename=item.get("filename", ""),
                    status=item.get("status", ""),
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                    changes=item.get("changes", 0),
                    patch=item.get("patch"),
                    previous_filename=item.get("previous_filename"),
                )
            )
        return files

    async def _fetch_commits(
        self, client: httpx.AsyncClient, pr_path: str
    ) -> list[PRCommit]:
        commits: list[PRCommit] = []
        async for item in self._paginate(client, f"{pr_path}/commits"):
            commit = item.get("commit") or {}
            author = commit.get("author") or {}
            commits.append(
                PRCommit(
                    sha=item.get("sha", ""),
                    message=commit.get("message", ""),
                    author=author.get("name"),
                    date=author.get("date"),
                )
            )
        return commits

    async def _paginate(self, client: httpx.AsyncClient, path: str):
        """遍历分页接口，逐条 yield JSON 项。"""
        page = 1
        while True:
            resp = await self._get(
                client, path, params={"per_page": 100, "page": page}
            )
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                yield item
            if len(batch) < 100:
                break
            page += 1

    async def _get(
        self, client: httpx.AsyncClient, path: str, params: dict | None = None
    ) -> httpx.Response:
        resp = await client.get(path, params=params)
        if resp.status_code == 404:
            raise GitHubError("PR 不存在或仓库为私有且 token 无访问权限（404）")
        if resp.status_code == 401:
            raise GitHubError("GitHub 鉴权失败，请检查 GITHUB_TOKEN（401）")
        if resp.status_code == 403:
            raise GitHubError(
                "GitHub 请求被拒绝，可能触发了速率限制，请稍后再试或配置 token（403）"
            )
        if resp.status_code >= 400:
            raise GitHubError(
                f"GitHub API 错误：{resp.status_code} {resp.text[:200]}"
            )
        return resp
