"""变更总结服务：抓取 PR → 构建 prompt → 调 DeepSeek(V3) → 解析为结构化总结。"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.models.github import PRRef
from app.models.llm import ChatMessage, TokenUsage
from app.models.review import PRSummary, SummaryResponse, to_file_changes
from app.services.cache import AnalysisCache
from app.services.deepseek_client import DeepSeekClient
from app.services.github_client import GitHubClient
from app.services.json_utils import extract_json
from app.services.prompts import (
    SUMMARY_META_MARKER,
    SUMMARY_SYSTEM_PROMPT,
    build_summary_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class SummaryStreamChunk:
    """总结流式产物：delta 为概述正文增量；result 非空表示分析完成的完整结果。"""

    delta: str = ""
    result: SummaryResponse | None = None


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

        resp = self._build_response(pr, summary, llm.model, llm.usage)

        if self._cache is not None:
            self._cache.set(key, resp.model_dump())

        return resp

    async def summarize_stream(
        self, ref: PRRef
    ) -> AsyncIterator[SummaryStreamChunk]:
        """流式总结：逐字产出概述正文增量，最后产出完整结果。

        缓存命中时不流式，直接产出 result（带 cached=True）。
        """
        pr = await self._github.fetch_pull_request(ref)

        key = AnalysisCache.make_key("summary", ref, pr.head_sha)
        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                cached["cached"] = True
                yield SummaryStreamChunk(result=SummaryResponse.model_validate(cached))
                return

        messages = [
            ChatMessage(role="system", content=SUMMARY_SYSTEM_PROMPT),
            ChatMessage(role="user", content=build_summary_prompt(pr)),
        ]

        buffer = ""
        emitted = 0
        usage = TokenUsage()
        model = ""
        marker = SUMMARY_META_MARKER

        async for chunk in self._deepseek.chat_stream(messages, temperature=0.2):
            if chunk.done:
                usage = chunk.usage or TokenUsage()
                model = chunk.model
                break
            buffer += chunk.delta
            idx = buffer.find(marker)
            if idx != -1:
                # 概述正文在分隔标记处结束：去掉标记前的尾随空白后做最后一次产出
                text = buffer[emitted:idx].rstrip()
                if text:
                    yield SummaryStreamChunk(delta=text)
                emitted = len(buffer)  # 标记及之后不再外显
                continue
            # 标记尚未出现，保留末尾可能正在拼接的部分标记，避免外显半截标记
            safe = max(0, len(buffer) - (len(marker) - 1))
            if safe > emitted:
                yield SummaryStreamChunk(delta=buffer[emitted:safe])
                emitted = safe

        summary = self._parse_summary(buffer)
        resp = self._build_response(pr, summary, model, usage)

        if self._cache is not None:
            self._cache.set(key, resp.model_dump())

        yield SummaryStreamChunk(result=resp)

    @staticmethod
    def _build_response(
        pr, summary: PRSummary, model: str, usage: TokenUsage
    ) -> SummaryResponse:
        return SummaryResponse(
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
            model=model,
            usage=usage,
        )

    @classmethod
    def _parse_summary(cls, content: str) -> PRSummary:
        """解析两段式总结：分隔标记前为概述正文，标记后为 key_changes/impact JSON。

        兼容旧的单 JSON 格式（无标记时回退为整段 JSON 或纯文本概述）。
        """
        idx = content.find(SUMMARY_META_MARKER)
        if idx == -1:
            try:
                data = extract_json(content)
            except ValueError:
                return PRSummary(overview=content.strip(), key_changes=[], impact="")
            return cls._summary_from_json(
                data, overview=str(data.get("overview", "")).strip()
            )

        overview = content[:idx].strip()
        rest = content[idx + len(SUMMARY_META_MARKER):]
        try:
            data = extract_json(rest)
        except ValueError:
            logger.warning("总结元信息 JSON 解析失败，仅保留概述正文")
            return PRSummary(overview=overview, key_changes=[], impact="")
        return cls._summary_from_json(data, overview=overview)

    @staticmethod
    def _summary_from_json(data: dict, *, overview: str) -> PRSummary:
        key_changes = data.get("key_changes") or []
        if not isinstance(key_changes, list):
            key_changes = [str(key_changes)]
        return PRSummary(
            overview=overview,
            key_changes=[str(x) for x in key_changes],
            impact=str(data.get("impact", "")).strip(),
        )
