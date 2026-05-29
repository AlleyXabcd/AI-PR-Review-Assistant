"""手动验证脚本：抓取一个 PR 并打印摘要。

用法：
    cd backend
    python -m app.scripts.fetch_pr https://github.com/owner/repo/pull/123
"""
from __future__ import annotations

import asyncio
import sys

from app.services.github_client import GitHubClient, GitHubError, parse_pr_url


async def _run(raw_url: str) -> int:
    try:
        ref = parse_pr_url(raw_url)
    except GitHubError as exc:
        print(f"[解析失败] {exc}")
        return 2

    print(f"目标 PR: {ref}")
    client = GitHubClient()
    try:
        pr = await client.fetch_pull_request(ref)
    except GitHubError as exc:
        print(f"[抓取失败] {exc}")
        return 1

    print(f"\n标题: {pr.title}")
    print(f"作者: {pr.author}  状态: {pr.state}")
    print(f"分支: {pr.head_branch} -> {pr.base_branch}")
    print(
        f"变更: +{pr.additions} -{pr.deletions}  "
        f"文件 {pr.changed_files}  提交 {len(pr.commits)}"
    )

    print("\n变更文件:")
    for f in pr.files:
        print(f"  [{f.status:8}] +{f.additions:<4} -{f.deletions:<4} {f.filename}")

    print("\n提交:")
    for c in pr.commits:
        first_line = c.message.splitlines()[0] if c.message else ""
        print(f"  {c.sha[:8]}  {first_line}")

    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python -m app.scripts.fetch_pr <github-pr-url>")
        raise SystemExit(2)
    raise SystemExit(asyncio.run(_run(sys.argv[1])))


if __name__ == "__main__":
    main()
