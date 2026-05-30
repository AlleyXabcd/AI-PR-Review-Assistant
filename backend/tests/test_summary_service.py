import pytest

from app.models.github import PRCommit, PRFile, PRRef, PullRequest
from app.models.llm import LLMResponse, TokenUsage
from app.services.summary_service import SummaryService


class _FakeGitHub:
    def __init__(self, pr: PullRequest):
        self._pr = pr

    async def fetch_pull_request(self, ref: PRRef) -> PullRequest:
        return self._pr


class _FakeDeepSeek:
    def __init__(self, content: str):
        self._content = content
        self.last_messages = None

    async def chat(self, messages, *, temperature=0.2, max_tokens=None):
        self.last_messages = messages
        return LLMResponse(
            content=self._content,
            model="deepseek-chat",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )


def _sample_pr() -> PullRequest:
    return PullRequest(
        ref=PRRef(owner="o", repo="r", number=1),
        title="Add caching",
        body="adds a cache layer",
        author="bob",
        state="open",
        base_branch="main",
        head_branch="feat-cache",
        base_sha="b1",
        head_sha="h1",
        additions=20,
        deletions=3,
        changed_files=2,
        html_url="https://github.com/o/r/pull/1",
        files=[
            PRFile(filename="cache.py", status="added", additions=20, deletions=0, patch="@@ +new"),
            PRFile(filename="app.py", status="modified", additions=0, deletions=3, patch="@@ -old"),
        ],
        commits=[PRCommit(sha="abc12345", message="add cache")],
    )


async def test_summarize_parses_structured_json():
    pr = _sample_pr()
    content = (
        '{"overview": "引入缓存层", '
        '"key_changes": ["新增 cache.py", "改造 app.py"], '
        '"impact": "需关注缓存失效"}'
    )
    svc = SummaryService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek(content))

    resp = await svc.summarize(pr.ref)

    assert resp.title == "Add caching"
    assert resp.summary.overview == "引入缓存层"
    assert resp.summary.key_changes == ["新增 cache.py", "改造 app.py"]
    assert resp.summary.impact == "需关注缓存失效"
    assert resp.changed_files == 2
    assert len(resp.files) == 2
    # patch 片段透传给前端用于 diff 高亮
    assert resp.files[0].patch == "@@ +new"
    assert resp.usage.total_tokens == 150


async def test_summarize_falls_back_on_bad_json():
    pr = _sample_pr()
    svc = SummaryService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek("纯文本无 JSON"))

    resp = await svc.summarize(pr.ref)

    assert resp.summary.overview == "纯文本无 JSON"
    assert resp.summary.key_changes == []
