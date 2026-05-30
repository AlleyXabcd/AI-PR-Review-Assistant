"""风险识别服务：抓取 PR → 构建 prompt → 调 DeepSeek(V3) → 解析为结构化风险列表。"""
from __future__ import annotations

import logging

from app.models.github import FileContext, PRRef, PullRequest
from app.models.llm import ChatMessage, TokenUsage
from app.models.review import (
    CATEGORIES,
    SEVERITIES,
    RiskItem,
    RisksResponse,
    to_file_changes,
)
from app.services.deepseek_client import DeepSeekClient, DeepSeekError
from app.services.github_client import GitHubClient, GitHubError
from app.services.json_utils import extract_json
from app.services.prompts import (
    REVIEW_SYSTEM_PROMPT,
    RISK_SYSTEM_PROMPT,
    build_review_prompt,
    build_risk_prompt,
)

logger = logging.getLogger(__name__)

# 拉取完整内容作为上下文的文件数上限（按变更量排序取前 N），控制请求体量与延迟
_MAX_CONTEXT_FILES = 10


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

        contexts = await self._collect_contexts(ref, pr)

        # 第一层：V3 全量分诊，快速产出结构化风险
        messages = [
            ChatMessage(role="system", content=RISK_SYSTEM_PROMPT),
            ChatMessage(role="user", content=build_risk_prompt(pr, contexts)),
        ]
        llm = await self._deepseek.chat(messages, temperature=0.2)
        risks = self._parse_risks(llm.content)

        usage = TokenUsage(
            prompt_tokens=llm.usage.prompt_tokens,
            completion_tokens=llm.usage.completion_tokens,
            total_tokens=llm.usage.total_tokens,
        )
        model = llm.model

        # 第二层：R1 仅对高危风险深度复查，确认/驳回误报/修正级别
        high_idx = [i for i, r in enumerate(risks) if r.severity == "high"]
        if high_idx:
            review_usage, review_model = await self._review_high_risks(
                pr, contexts, risks, high_idx
            )
            if review_usage is not None:
                usage.prompt_tokens += review_usage.prompt_tokens
                usage.completion_tokens += review_usage.completion_tokens
                usage.total_tokens += review_usage.total_tokens
                model = f"{model} + {review_model}"

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
            model=model,
            usage=usage,
        )

    async def _review_high_risks(
        self,
        pr: PullRequest,
        contexts: list[FileContext],
        risks: list[RiskItem],
        high_idx: list[int],
    ) -> tuple[TokenUsage | None, str]:
        """用 R1 复查高危风险，原地修改 risks（reject 的剔除、adjust 的修正）。

        返回 (本次 usage, 模型名)；复查调用失败时返回 (None, "") 并保留 V3 结果。
        """
        high_risks = [risks[i] for i in high_idx]
        messages = [
            ChatMessage(role="system", content=REVIEW_SYSTEM_PROMPT),
            ChatMessage(
                role="user", content=build_review_prompt(high_risks, pr, contexts)
            ),
        ]
        try:
            llm = await self._deepseek.reason(messages)
        except DeepSeekError as exc:
            logger.warning("R1 复查调用失败，保留 V3 结果：%s", exc)
            return None, ""

        verdicts = self._parse_reviews(llm.content)

        # 按复查结果更新：reject 标记剔除，adjust/confirm 更新字段
        drop: set[int] = set()
        for local_i, risk in enumerate(high_risks):
            v = verdicts.get(local_i)
            if v is None:
                continue
            verdict = v.get("verdict")
            if verdict == "reject":
                drop.add(high_idx[local_i])
                continue
            if "confidence" in v:
                risk.confidence = v["confidence"]
            if v.get("detail"):
                risk.detail = v["detail"]
            if v.get("suggestion"):
                risk.suggestion = v["suggestion"]
            if verdict == "adjust":
                sev = v.get("severity")
                if sev in SEVERITIES:
                    risk.severity = sev

        if drop:
            kept = [r for i, r in enumerate(risks) if i not in drop]
            risks[:] = kept

        return llm.usage, llm.model

    @staticmethod
    def _parse_reviews(content: str) -> dict[int, dict]:
        """解析 R1 复查输出为 {index: {verdict, severity?, confidence?, ...}}。"""
        try:
            data = extract_json(content)
        except ValueError:
            logger.warning("R1 复查 JSON 解析失败，保留 V3 结果")
            return {}

        raw = data.get("reviews")
        if not isinstance(raw, list):
            return {}

        out: dict[int, dict] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            if not isinstance(idx, int) or isinstance(idx, bool):
                continue
            entry: dict = {}
            verdict = str(item.get("verdict", "")).strip().lower()
            entry["verdict"] = verdict if verdict in {"confirm", "reject", "adjust"} else "confirm"

            sev = str(item.get("severity", "")).strip().lower()
            if sev in SEVERITIES:
                entry["severity"] = sev

            if "confidence" in item:
                try:
                    c = float(item["confidence"])
                    entry["confidence"] = min(1.0, max(0.0, c))
                except (TypeError, ValueError):
                    pass

            detail = str(item.get("detail", "")).strip()
            if detail:
                entry["detail"] = detail
            suggestion = str(item.get("suggestion", "")).strip()
            if suggestion:
                entry["suggestion"] = suggestion

            out[idx] = entry
        return out

    async def _collect_contexts(self, ref: PRRef, pr: PullRequest) -> list[FileContext]:
        """拉取变更文件在 head 版本的完整内容，作为跨文件上下文。

        只取非删除、且有文本 diff 的文件，按变更量取前 N；拉取失败降级为空（仅用 diff）。
        """
        candidates = [
            f
            for f in pr.files
            if f.status != "removed" and f.patch
        ]
        candidates.sort(key=lambda f: f.changes, reverse=True)
        paths = [f.filename for f in candidates[:_MAX_CONTEXT_FILES]]
        if not paths:
            return []

        try:
            return await self._github.fetch_file_contents(ref, paths, pr.head_sha)
        except GitHubError as exc:
            logger.warning("拉取文件上下文失败，降级为仅使用 diff：%s", exc)
            return []

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
