"""评论回写服务：复用已有分析结果 → 拼 Markdown 评论 → 预览或发送到 GitHub PR。

设计取舍：
- 复用 SummaryService / RiskService（均带缓存，key=PR+head_sha），
  刚分析过的 PR 不会重复调用模型；
- dry_run=True 只返回拼好的评论正文供前端预览，绝不触达 GitHub 写接口；
- dry_run=False 才真正调用 post_issue_comment，避免误发到真实 PR。
"""
from __future__ import annotations

from app.models.github import PRRef
from app.models.review import (
    RiskItem,
    RisksResponse,
    SummaryResponse,
    WritebackResponse,
)
from app.services.cache import AnalysisCache
from app.services.deepseek_client import DeepSeekClient
from app.services.github_client import GitHubClient
from app.services.risk_service import RiskService
from app.services.summary_service import SummaryService

_SEVERITY_LABEL = {"high": "高危", "medium": "中危", "low": "低危"}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
_CATEGORY_LABEL = {
    "security": "安全",
    "performance": "性能",
    "correctness": "正确性",
    "maintainability": "可维护性",
}


class WritebackService:
    def __init__(
        self,
        github: GitHubClient | None = None,
        deepseek: DeepSeekClient | None = None,
        cache: AnalysisCache | None = None,
    ) -> None:
        self._github = github or GitHubClient()
        # summary / risk 服务共享同一 github + deepseek + cache 实例
        self._summary = SummaryService(github=self._github, deepseek=deepseek, cache=cache)
        self._risk = RiskService(github=self._github, deepseek=deepseek, cache=cache)

    async def build(self, ref: PRRef, *, dry_run: bool = True) -> WritebackResponse:
        summary = await self._summary.summarize(ref)
        risks = await self._risk.detect(ref)

        body = self._format_comment(summary, risks)
        model = self._merge_model(summary.model, risks.model)

        if dry_run:
            return WritebackResponse(
                posted=False, dry_run=True, body=body, comment_url="", model=model
            )

        comment_url = await self._github.post_issue_comment(ref, body)
        return WritebackResponse(
            posted=True, dry_run=False, body=body, comment_url=comment_url, model=model
        )

    @staticmethod
    def _merge_model(summary_model: str, risk_model: str) -> str:
        parts = [m for m in (summary_model, risk_model) if m]
        # 两个阶段模型可能相同，去重保留顺序
        seen: list[str] = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return " / ".join(seen)

    @classmethod
    def _format_comment(
        cls, summary: SummaryResponse, risks: RisksResponse
    ) -> str:
        lines: list[str] = []
        lines.append("## 🤖 AI PR Review 助手")
        lines.append("")
        lines.append(f"**变更概述**：{summary.summary.overview or '（无）'}")

        if summary.summary.key_changes:
            lines.append("")
            lines.append("**关键改动**")
            for k in summary.summary.key_changes:
                lines.append(f"- {k}")

        if summary.summary.impact:
            lines.append("")
            lines.append(f"**影响与关注点**：{summary.summary.impact}")

        lines.append("")
        lines.append(cls._format_risks(risks.risks))

        lines.append("")
        lines.append("---")
        model = cls._merge_model(summary.model, risks.model)
        lines.append(
            f"<sub>由 AI PR Review 助手生成 · 模型 {model or '未知'} · 仅供参考</sub>"
        )
        return "\n".join(lines)

    @classmethod
    def _format_risks(cls, risks: list[RiskItem]) -> str:
        if not risks:
            return "**风险识别**：未发现明显风险。 ✅"

        ordered = sorted(risks, key=lambda r: _SEVERITY_ORDER.get(r.severity, 3))
        out = [f"**风险识别（{len(risks)} 个风险点）**", ""]
        for r in ordered:
            sev = _SEVERITY_LABEL.get(r.severity, r.severity)
            cat = _CATEGORY_LABEL.get(r.category, r.category)
            loc = f"`{r.file}:{r.line}`" if r.line is not None else f"`{r.file}`"
            out.append(f"- **[{sev}·{cat}]** {r.title} — {loc}")
            if r.detail:
                out.append(f"  - 说明：{r.detail}")
            if r.suggestion:
                out.append(f"  - 建议：{r.suggestion}")
        return "\n".join(out)
