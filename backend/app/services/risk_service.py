"""风险识别服务：抓取 PR → 构建 prompt → 调 DeepSeek(V3) → 解析为结构化风险列表。"""
from __future__ import annotations

import logging

from app.models.github import PRRef
from app.models.llm import ChatMessage
from app.models.review import (
    CATEGORIES,
    SEVERITIES,
    RiskItem,
    RisksResponse,
    to_file_changes,
)
from app.services.deepseek_client import DeepSeekClient
from app.services.github_client import GitHubClient
from app.services.json_utils import extract_json
from app.services.prompts import RISK_SYSTEM_PROMPT, build_risk_prompt

logger = logging.getLogger(__name__)


class RiskService:
    def __init__(
        self,
        github: GitHubClient | None = None,
        deepseek: DeepSeekClient | None = None,
    ) -> None:
        self._github = github or GitHubClient()
        self._deepseek = deepseek or DeepSeekClient()

    async def detect(self, ref: PRRef) -> RisksResponse:
        pr = await self._github.fetch_pull_request(ref)

        messages = [
            ChatMessage(role="system", content=RISK_SYSTEM_PROMPT),
            ChatMessage(role="user", content=build_risk_prompt(pr)),
        ]
        llm = await self._deepseek.chat(messages, temperature=0.2)

        risks = self._parse_risks(llm.content)

        return RisksResponse(
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
            risks=risks,
            model=llm.model,
            usage=llm.usage,
        )

    @classmethod
    def _parse_risks(cls, content: str) -> list[RiskItem]:
        try:
            data = extract_json(content)
        except ValueError:
            logger.warning("风险 JSON 解析失败，降级为空风险列表")
            return []

        raw = data.get("risks")
        if not isinstance(raw, list):
            logger.warning("风险输出缺少 risks 数组，降级为空风险列表")
            return []

        risks: list[RiskItem] = []
        for item in raw:
            normalized = cls._normalize_item(item)
            if normalized is not None:
                risks.append(normalized)
        return risks

    @staticmethod
    def _normalize_item(item: object) -> RiskItem | None:
        if not isinstance(item, dict):
            return None

        file = str(item.get("file", "")).strip()
        title = str(item.get("title", "")).strip()
        # file 与 title 是定位风险的最小信息，缺失则视为无效项丢弃
        if not file or not title:
            return None

        severity = str(item.get("severity", "")).strip().lower()
        if severity not in SEVERITIES:
            severity = "low"

        category = str(item.get("category", "")).strip().lower()
        if category not in CATEGORIES:
            category = "correctness"

        line = item.get("line")
        if not isinstance(line, int) or isinstance(line, bool) or line <= 0:
            line = None

        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = min(1.0, max(0.0, confidence))

        return RiskItem(
            file=file,
            line=line,
            severity=severity,
            category=category,
            title=title,
            detail=str(item.get("detail", "")).strip(),
            suggestion=str(item.get("suggestion", "")).strip(),
            confidence=confidence,
        )
