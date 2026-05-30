"""变更总结服务：抓取 PR → 构建 prompt → 调 DeepSeek(V3) → 解析为结构化总结。"""
from __future__ import annotations

import logging

from app.models.github import PRRef
from app.models.llm import ChatMessage
from app.models.review import PRSummary, SummaryResponse, to_file_changes
from app.services.cache import AnalysisCache
from app.services.deepseek_client import DeepSeekClient
from app.services.github_client import GitHubClient
from app.services.json_utils import extract_json
from app.services.prompts import (
    SUMMARY_SYSTEM_PROMPT,
    build_summary_prompt,
)

logger = logging.getLogger(__name__)


class SummaryService:
    def __init__(
        self,
        github: GitHubClient | None = None,
        deepseek: DeepSeekClient | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self._github = github or GitHubClient()
        self._deepseek = deepseek or DeepSeekClient()
        self._cache = cache

    async def summarize(self, ref: PRRef) -> SummaryResponse:
        pr = await self._github.fetch_pull_request(ref)

        # 以 head_sha 为版本标识查缓存：命中则直接返回历史分析结果，不再调用模型
        key = AnalysisCache.make_key("summary", ref, pr.head_sha)
        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                cached["cached"] = True
                return SummaryResponse.model_validate(cached)

        messages = [
            ChatMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
            ChatMessage(role="user", content=build_summary_prompt(pr)),
        ]
        llm = await self._deepseek.chat(messages, temperature=0.2)

        summary = self._parse_summary(llm.content)

        resp = SummaryResponse(
            title=pr.title,
            author=pr.author,
            state=pr.state,
            base_branch=pr.base_branch,
            head_branch=pr.head_branch,
            html_url=pr.html_url,
            additions=pr.additions,
            deletions=pr.deletions,
            changed_files=pr.changed_files,
            files=to_file_changes(pr.files),
            commits=pr.commits,
            summary=summary,
            model=llm.model,
            usage=llm.usage,
        )

        if self._cache is not None:
            self._cache.set(key, resp.model_dump())

        return resp

    @staticmethod
    def _parse_summary(content: str) -> PRSummary:
        try:
            data = extract_json(content)
        except ValueError:
            logger.warning("总结 JSON 解析失败，降级为纯文本 overview")
            return PRSummary(overview=content.strip(), key_changes=[], impact="")

        key_changes = data.get("key_changes") or []
        if not isinstance(key_changes, list):
            key_changes = [str(key_changes)]

        return PRSummary(
            overview=str(data.get("overview", "")).strip(),
            key_changes=[str(x) for x in key_changes],
            impact=str(data.get("impact", "")).strip(),
        )
