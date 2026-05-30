import pytest

from app.models.github import PRCommit, PRFile, PRRef, PullRequest
from app.models.llm import LLMResponse, TokenUsage
from app.services.risk_service import RiskService


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
        title="Add login",
        body="adds login handler",
        author="bob",
        state="open",
        base_branch="main",
        head_branch="feat-login",
        base_sha="b1",
        head_sha="h1",
        additions=20,
        deletions=3,
        changed_files=1,
        html_url="https://github.com/o/r/pull/1",
        files=[
            PRFile(
                filename="auth.py",
                status="modified",
                additions=20,
                deletions=3,
                patch="@@ -1 +1 @@\n+query = f\"select * from u where id={uid}\"",
            ),
        ],
        commits=[PRCommit(sha="abc12345", message="add login")],
    )


async def test_detect_parses_structured_risks():
    pr = _sample_pr()
    content = (
        '{"risks": [{"file": "auth.py", "line": 12, "severity": "high", '
        '"category": "security", "title": "SQL 注入", "detail": "拼接用户输入", '
        '"suggestion": "使用参数化查询", "confidence": 0.9}]}'
    )
    svc = RiskService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek(content))

    resp = await svc.detect(pr.ref)

    assert resp.title == "Add login"
    assert resp.changed_files == 1
    assert len(resp.risks) == 1
    risk = resp.risks[0]
    assert risk.file == "auth.py"
    assert risk.line == 12
    assert risk.severity == "high"
    assert risk.category == "security"
    assert risk.title == "SQL 注入"
    assert risk.confidence == 0.9
    assert resp.usage.total_tokens == 150


async def test_detect_normalizes_invalid_enums_and_confidence():
    pr = _sample_pr()
    content = (
        '{"risks": [{"file": "auth.py", "title": "可疑代码", '
        '"severity": "CRITICAL", "category": "style", '
        '"line": "n/a", "confidence": 5}]}'
    )
    svc = RiskService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek(content))

    resp = await svc.detect(pr.ref)

    assert len(resp.risks) == 1
    risk = resp.risks[0]
    # 非法 severity / category 落到默认值
    assert risk.severity == "low"
    assert risk.category == "correctness"
    # 非整数行号归一化为 None
    assert risk.line is None
    # 越界 confidence 被裁剪到 [0, 1]
    assert risk.confidence == 1.0


async def test_detect_drops_items_missing_file_or_title():
    pr = _sample_pr()
    content = (
        '{"risks": ['
        '{"file": "auth.py", "title": "有效项"}, '
        '{"file": "", "title": "缺文件"}, '
        '{"file": "x.py", "title": ""}, '
        '"not-a-dict"'
        ']}'
    )
    svc = RiskService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek(content))

    resp = await svc.detect(pr.ref)

    assert len(resp.risks) == 1
    assert resp.risks[0].title == "有效项"


async def test_detect_empty_risks():
    pr = _sample_pr()
    svc = RiskService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek('{"risks": []}'))

    resp = await svc.detect(pr.ref)

    assert resp.risks == []


async def test_detect_falls_back_on_bad_json():
    pr = _sample_pr()
    svc = RiskService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek("模型没有返回 JSON"))

    resp = await svc.detect(pr.ref)

    assert resp.risks == []


async def test_detect_falls_back_when_risks_not_list():
    pr = _sample_pr()
    svc = RiskService(github=_FakeGitHub(pr), deepseek=_FakeDeepSeek('{"risks": "oops"}'))

    resp = await svc.detect(pr.ref)

    assert resp.risks == []
