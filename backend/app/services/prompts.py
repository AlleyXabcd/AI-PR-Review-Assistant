"""Prompt 构建：把 PullRequest 渲染为发送给模型的文本。

集中管理 prompt 模板，便于后续风险识别 / 行级建议复用 diff 渲染逻辑。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.github import FileContext, PullRequest

if TYPE_CHECKING:
    from app.models.review import RiskItem

# 控制单次请求体量，避免超长输入：每个文件 patch 截断上限（字符）
_MAX_PATCH_CHARS = 6000
# 参与总结的文件数量上限（按变更量排序后取前 N）
_MAX_FILES = 50
# 单个上下文文件在 prompt 中的渲染上限（字符）
_MAX_CONTEXT_CHARS = 12000

SUMMARY_SYSTEM_PROMPT = (
    "你是一位资深的代码评审专家。请阅读给定的 GitHub Pull Request 变更，"
    "用简洁、准确的中文总结本次改动。不要臆测未给出的代码，只基于提供的 diff 与元信息。"
    "请严格按要求的两段式格式输出。"
)

# 总结分隔标记：标记前为可逐字流式直显的概述正文，标记后为结构化元信息 JSON。
SUMMARY_META_MARKER = "===META==="

SUMMARY_OUTPUT_SPEC = f"""请按如下两段式输出，分两部分：

第一部分：直接写一段自然语言的「概述」，说明本次 PR 的意图与整体改动。只写正文，不要加任何标题、前缀或 JSON。

然后另起一行，输出且仅输出这一行分隔标记：
{SUMMARY_META_MARKER}

第二部分：在分隔标记之后输出如下 JSON（不要使用 markdown 代码块包裹）：
{{
  "key_changes": ["关键改动要点1", "关键改动要点2", "..."],
  "impact": "本次改动可能的影响、风险或需要评审者重点关注的地方"
}}"""


def _render_files(pr: PullRequest) -> str:
    files = sorted(pr.files, key=lambda f: f.changes, reverse=True)[:_MAX_FILES]
    blocks: list[str] = []
    for f in files:
        header = (
            f"文件: {f.filename}  ({f.status}, +{f.additions} -{f.deletions})"
        )
        if not f.patch:
            blocks.append(f"{header}\n[无文本 diff（可能为二进制或过大文件）]")
            continue
        patch = f.patch
        if len(patch) > _MAX_PATCH_CHARS:
            patch = patch[:_MAX_PATCH_CHARS] + "\n... [diff 过长，已截断]"
        blocks.append(f"{header}\n```diff\n{patch}\n```")
    return "\n\n".join(blocks)


def _render_commits(pr: PullRequest) -> str:
    lines = []
    for c in pr.commits[:30]:
        first = c.message.splitlines()[0] if c.message else ""
        lines.append(f"- {c.sha[:8]} {first}")
    return "\n".join(lines) if lines else "（无提交信息）"


def _render_meta(pr: PullRequest) -> str:
    meta = (
        f"# PR 元信息\n"
        f"标题: {pr.title}\n"
        f"作者: {pr.author}\n"
        f"分支: {pr.head_branch} -> {pr.base_branch}\n"
        f"变更规模: +{pr.additions} -{pr.deletions}，共 {pr.changed_files} 个文件\n"
    )
    if pr.body:
        body = pr.body if len(pr.body) <= 2000 else pr.body[:2000] + " ...[已截断]"
        meta += f"\n# PR 描述\n{body}\n"
    return meta


def build_summary_prompt(pr: PullRequest) -> str:
    """构建变更总结的 user prompt。"""
    meta = _render_meta(pr)
    commits = f"\n# 提交记录\n{_render_commits(pr)}\n"
    files = f"\n# 变更内容（diff）\n{_render_files(pr)}\n"

    return f"{meta}{commits}{files}\n{SUMMARY_OUTPUT_SPEC}"


RISK_SYSTEM_PROMPT = (
    "你是一位经验丰富的代码安全与质量评审专家。请仔细审查给定 GitHub Pull Request "
    "的代码变更，找出其中真实存在的风险点。"
    "我可能会额外提供变更文件的完整内容作为上下文：请结合上下文理解被修改代码的"
    "作用与调用关系，但你的风险结论应聚焦于本次 diff 改动的代码，不要去评审未改动的既有代码。"
    "只基于提供的信息判断，不要臆测未给出的代码。"
    "宁缺毋滥：仅在你较有把握时才报告风险，没有发现风险时返回空数组，不要为了凑数而编造。"
    "请严格按要求的 JSON 格式输出，不要输出 JSON 以外的任何内容。"
)

RISK_OUTPUT_SPEC = """请输出如下 JSON（仅输出 JSON，不要使用 markdown 代码块包裹）：
{
  "risks": [
    {
      "file": "出现风险的文件路径",
      "line": 行号（diff 中新增/修改代码所在的行号，整数；无法确定时用 null）,
      "severity": "high | medium | low（严重级别）",
      "category": "security | performance | correctness | maintainability（风险分类）",
      "title": "一句话概括该风险",
      "detail": "为什么这是个问题，结合具体代码说明",
      "suggestion": "可执行的修改建议",
      "confidence": 0.0~1.0 之间的小数，表示你对该判断的置信度
    }
  ]
}
没有发现任何风险时输出 {"risks": []}。"""


def _render_contexts(contexts: list[FileContext]) -> str:
    blocks: list[str] = []
    for c in contexts:
        content = c.content
        if len(content) > _MAX_CONTEXT_CHARS:
            content = content[:_MAX_CONTEXT_CHARS] + "\n... [文件过长，已截断]"
        blocks.append(f"文件: {c.filename}\n```\n{content}\n```")
    return "\n\n".join(blocks)


def build_risk_prompt(
    pr: PullRequest, contexts: list[FileContext] | None = None
) -> str:
    """构建风险识别的 user prompt。

    contexts 为变更文件在 head 版本的完整内容，用于补充跨文件上下文；为空则仅基于 diff。
    """
    meta = _render_meta(pr)
    files = f"\n# 变更内容（diff）\n{_render_files(pr)}\n"
    context_block = ""
    if contexts:
        context_block = (
            f"\n# 变更文件完整内容（改动后版本，供理解上下文）\n"
            f"{_render_contexts(contexts)}\n"
        )

    return f"{meta}{files}{context_block}\n{RISK_OUTPUT_SPEC}"


REVIEW_SYSTEM_PROMPT = (
    "你是一位极其严谨的资深安全评审专家，擅长深度推理。"
    "下面会给你若干由初筛模型标为「高危」的风险点，以及对应的代码变更与上下文。"
    "请逐条复核：判断该风险是否真实成立。"
    "对每一条给出裁决：confirm（确认成立）、reject（实为误报，应剔除）、"
    "adjust（成立但严重级别或描述需修正）。"
    "复核时要结合上下文严格推理，剔除初筛模型因缺乏上下文产生的误报。"
    "请严格按要求的 JSON 格式输出，不要输出 JSON 以外的任何内容。"
)

REVIEW_OUTPUT_SPEC = """请输出如下 JSON（仅输出 JSON，不要使用 markdown 代码块包裹）：
{
  "reviews": [
    {
      "index": 待复核风险点的编号（与下方列表一致，整数）,
      "verdict": "confirm | reject | adjust",
      "severity": "high | medium | low（verdict 为 adjust 时给出修正后的级别，否则可省略）",
      "confidence": 0.0~1.0（你复核后的置信度）,
      "detail": "复核理由（尤其 reject/adjust 时说明为什么）",
      "suggestion": "修正后的修改建议（可选）"
    }
  ]
}
请对列表中的每一个编号都给出一条复核结果。"""


def _render_high_risks(high_risks: list["RiskItem"]) -> str:
    lines: list[str] = []
    for i, r in enumerate(high_risks):
        loc = f"{r.file}:{r.line}" if r.line is not None else r.file
        lines.append(
            f"[{i}] 位置: {loc}\n"
            f"    分类: {r.category}\n"
            f"    标题: {r.title}\n"
            f"    说明: {r.detail}"
        )
    return "\n".join(lines)


def build_review_prompt(
    high_risks: list["RiskItem"],
    pr: PullRequest,
    contexts: list[FileContext] | None = None,
) -> str:
    """构建 R1 深度复查的 user prompt。"""
    meta = _render_meta(pr)
    risks_block = f"\n# 待复核的高危风险点\n{_render_high_risks(high_risks)}\n"
    files = f"\n# 变更内容（diff）\n{_render_files(pr)}\n"
    context_block = ""
    if contexts:
        context_block = (
            f"\n# 变更文件完整内容（改动后版本，供理解上下文）\n"
            f"{_render_contexts(contexts)}\n"
        )

    return f"{meta}{risks_block}{files}{context_block}\n{REVIEW_OUTPUT_SPEC}"
