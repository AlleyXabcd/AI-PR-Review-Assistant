"""Prompt 构建：把 PullRequest 渲染为发送给模型的文本。

集中管理 prompt 模板，便于后续风险识别 / 行级建议复用 diff 渲染逻辑。
"""
from __future__ import annotations

from app.models.github import PullRequest

# 控制单次请求体量，避免超长输入：每个文件 patch 截断上限（字符）
_MAX_PATCH_CHARS = 6000
# 参与总结的文件数量上限（按变更量排序后取前 N）
_MAX_FILES = 50

SUMMARY_SYSTEM_PROMPT = (
    "你是一位资深的代码评审专家。请阅读给定的 GitHub Pull Request 变更，"
    "用简洁、准确的中文总结本次改动。不要臆测未给出的代码，只基于提供的 diff 与元信息。"
    "请严格按要求的 JSON 格式输出，不要输出 JSON 以外的任何内容。"
)

SUMMARY_OUTPUT_SPEC = """请输出如下 JSON（仅输出 JSON，不要使用 markdown 代码块包裹）：
{
  "overview": "一段话概述本次 PR 的意图与整体改动",
  "key_changes": ["关键改动要点1", "关键改动要点2", "..."],
  "impact": "本次改动可能的影响、风险或需要评审者重点关注的地方"
}"""


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
    "的代码变更，找出其中真实存在的风险点。只基于提供的 diff 判断，不要臆测未给出的代码。"
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


def build_risk_prompt(pr: PullRequest) -> str:
    """构建风险识别的 user prompt。"""
    meta = _render_meta(pr)
    files = f"\n# 变更内容（diff）\n{_render_files(pr)}\n"

    return f"{meta}{files}\n{RISK_OUTPUT_SPEC}"
