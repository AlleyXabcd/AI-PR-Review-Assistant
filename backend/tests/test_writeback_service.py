import pytest

from app.models.github import PRRef
from app.models.llm import TokenUsage
from app.models.review import PRSummary, RiskItem, RisksResponse, SummaryResponse
from app.services.writeback_service import WritebackService

_REF = PRRef(owner="o", repo="r", number=1)


def _summary() -> SummaryResponse:
    return SummaryResponse(
        title="Add login",
        author="bob",
        state="open",
        base_branch="main",
        head_branch="feat",
        html_url="https://github.com/o/r/pull/1",
        summary=PRSummary(
            overview="新增登录功能",
            key_changes=["新增 auth.py", "接入会话中间件"],
            impact="关注会话过期处理",
        ),
        model="deepseek-chat",
        usage=TokenUsage(total_tokens=150),
    )


def _risks(items: list[RiskItem]) -> RisksResponse:
    return RisksResponse(
        title="Add login",
        state="open",
        base_branch="main",
        head_branch="feat",
        risks=items,
        model="deepseek-chat + deepseek-reasoner",
        usage=TokenUsage(total_tokens=300),
    )


class _FakeSummarySvc:
    def __init__(self, resp: SummaryResponse):
        self._resp = resp

    async def summarize(self, ref):
        return self._resp


class _FakeRiskSvc:
    def __init__(self, resp: RisksResponse):
        self._resp = resp

    async def detect(self, ref):
        return self._resp


class _FakeGitHub:
    def __init__(self):
        self.posted: tuple[PRRef, str] | None = None

    async def post_issue_comment(self, ref, body):
        self.posted = (ref, body)
        return "https://github.com/o/r/pull/1#issuecomment-1"


def _service(summary, risks, github) -> WritebackService:
    svc = WritebackService()
    svc._summary = _FakeSummarySvc(summary)
    svc._risk = _FakeRiskSvc(risks)
    svc._github = github
    return svc


async def test_dry_run_returns_preview_without_posting():
    github = _FakeGitHub()
    risk = RiskItem(
        file="auth.py",
        line=12,
        severity="high",
        category="security",
        title="SQL 注入",
        detail="拼接用户输入",
        suggestion="使用参数化查询",
        confidence=0.9,
    )
    svc = _service(_summary(), _risks([risk]), github)

    resp = await svc.build(_REF, dry_run=True)

    assert resp.dry_run is True
    assert resp.posted is False
    assert resp.comment_url == ""
    # 预览正文包含概述、关键改动、风险定位
    assert "新增登录功能" in resp.body
    assert "新增 auth.py" in resp.body
    assert "高危" in resp.body and "安全" in resp.body
    assert "`auth.py:12`" in resp.body
    # dry_run 不触达 GitHub 写接口
    assert github.posted is None


async def test_real_post_calls_github_and_returns_url():
    github = _FakeGitHub()
    svc = _service(_summary(), _risks([]), github)

    resp = await svc.build(_REF, dry_run=False)

    assert resp.posted is True
    assert resp.dry_run is False
    assert resp.comment_url.endswith("#issuecomment-1")
    # 真正发送时把正文交给 GitHub 客户端
    assert github.posted is not None
    ref, body = github.posted
    assert ref == _REF
    assert "未发现明显风险" in body


async def test_no_risks_renders_clean_message():
    github = _FakeGitHub()
    svc = _service(_summary(), _risks([]), github)

    resp = await svc.build(_REF, dry_run=True)

    assert "未发现明显风险" in resp.body


def test_merge_model_dedupes():
    assert WritebackService._merge_model("a", "a") == "a"
    assert WritebackService._merge_model("a", "b") == "a / b"
    assert WritebackService._merge_model("", "b") == "b"
