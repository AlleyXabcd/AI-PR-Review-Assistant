import pytest

from app.models.github import FileContext, PRCommit, PRFile, PRRef, PullRequest
from app.models.llm import LLMResponse, TokenUsage
from app.services.cache import AnalysisCache
from app.services.risk_service import RiskService


class _FakeGitHub:
    def __init__(self, pr: PullRequest, contexts: list[FileContext] | None = None):
        self._pr = pr
        self._contexts = contexts or []
        self.context_call: tuple[list[str], str] | None = None

    async def fetch_pull_request(self, ref: PRRef) -> PullRequest:
        return self._pr

    async def fetch_file_contents(
        self, ref: PRRef, paths: list[str], sha: str
    ) -> list[FileContext]:
        self.context_call = (paths, sha)
        return self._contexts


class _FakeDeepSeek:
    def __init__(self, content: str, reason_content: str | None = None):
        self._content = content
        self._reason_content = reason_content
        self.last_messages = None
        self.reason_messages = None
        self.reason_called = False
        self.chat_calls = 0

    async def chat(self, messages, *, temperature=0.2, max_tokens=None):
        self.chat_calls += 1
        self.last_messages = messages
        return LLMResponse(
            content=self._content,
            model="deepseek-chat",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

    async def reason(self, messages, *, max_tokens=None):
        self.reason_called = True
        self.reason_messages = messages
        return LLMResponse(
            content=self._reason_content or '{"reviews": []}',
            model="deepseek-reasoner",
            reasoning="思考过程",
            usage=TokenUsage(prompt_tokens=200, completion_tokens=80, total_tokens=280),
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
        '{"risks": [{"file": "auth.py", "line": 12, "severity": "medium", '
        '"category": "security", "title": "SQL 注入", "detail": "拼接用户输入", '
        '"suggestion": "使用参数化查询", "confidence": 0.9}]}'
    )
    deepseek = _FakeDeepSeek(content)
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    resp = await svc.detect(pr.ref)

    assert resp.title == "Add login"
    assert resp.changed_files == 1
    assert len(resp.risks) == 1
    risk = resp.risks[0]
    assert risk.file == "auth.py"
    assert risk.line == 12
    assert risk.severity == "medium"
    assert risk.category == "security"
    assert risk.title == "SQL 注入"
    assert risk.confidence == 0.9
    # 无高危风险，不触发 R1 第二层
    assert deepseek.reason_called is False
    assert resp.usage.total_tokens == 150
    assert resp.model == "deepseek-chat"


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


async def test_detect_injects_file_context_into_prompt():
    pr = _sample_pr()
    contexts = [FileContext(filename="auth.py", content="def login(uid):\n    ...")]
    github = _FakeGitHub(pr, contexts=contexts)
    deepseek = _FakeDeepSeek('{"risks": []}')
    svc = RiskService(github=github, deepseek=deepseek)

    await svc.detect(pr.ref)

    # 用 head_sha 拉取变更文件全文
    assert github.context_call == (["auth.py"], "h1")
    # 文件全文被注入到发给模型的 user prompt
    user_prompt = deepseek.last_messages[1].content
    assert "变更文件完整内容" in user_prompt
    assert "def login(uid):" in user_prompt


async def test_detect_skips_removed_files_for_context():
    pr = _sample_pr()
    pr.files.append(
        PRFile(filename="old.py", status="removed", additions=0, deletions=9, patch=None)
    )
    github = _FakeGitHub(pr)
    svc = RiskService(github=github, deepseek=_FakeDeepSeek('{"risks": []}'))

    await svc.detect(pr.ref)

    # 删除文件与无 patch 文件不参与上下文拉取
    assert github.context_call == (["auth.py"], "h1")


# ---- 双层分析：V3 分诊 → R1 复查高危 ----

_HIGH_RISK = (
    '{"risks": [{"file": "auth.py", "line": 12, "severity": "high", '
    '"category": "security", "title": "SQL 注入", "detail": "拼接用户输入", '
    '"suggestion": "改用参数化查询", "confidence": 0.8}]}'
)


async def test_review_confirms_high_risk():
    pr = _sample_pr()
    reason = '{"reviews": [{"index": 0, "verdict": "confirm", "confidence": 0.95}]}'
    deepseek = _FakeDeepSeek(_HIGH_RISK, reason_content=reason)
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    resp = await svc.detect(pr.ref)

    assert deepseek.reason_called is True
    assert len(resp.risks) == 1
    assert resp.risks[0].severity == "high"
    assert resp.risks[0].confidence == 0.95
    # 两次调用 usage 累加，model 记录双模型
    assert resp.usage.total_tokens == 150 + 280
    assert resp.model == "deepseek-chat + deepseek-reasoner"


async def test_review_rejects_false_positive():
    pr = _sample_pr()
    reason = '{"reviews": [{"index": 0, "verdict": "reject", "detail": "有上层校验，误报"}]}'
    deepseek = _FakeDeepSeek(_HIGH_RISK, reason_content=reason)
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    resp = await svc.detect(pr.ref)

    # 被 R1 判定为误报的高危风险从列表剔除
    assert resp.risks == []
    assert resp.usage.total_tokens == 150 + 280


async def test_review_adjusts_severity():
    pr = _sample_pr()
    reason = (
        '{"reviews": [{"index": 0, "verdict": "adjust", "severity": "low", '
        '"detail": "影响有限", "suggestion": "可选优化"}]}'
    )
    deepseek = _FakeDeepSeek(_HIGH_RISK, reason_content=reason)
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    resp = await svc.detect(pr.ref)

    assert len(resp.risks) == 1
    risk = resp.risks[0]
    assert risk.severity == "low"
    assert risk.detail == "影响有限"
    assert risk.suggestion == "可选优化"


async def test_review_skipped_when_no_high_risk():
    pr = _sample_pr()
    content = (
        '{"risks": [{"file": "auth.py", "severity": "low", '
        '"category": "maintainability", "title": "命名"}]}'
    )
    deepseek = _FakeDeepSeek(content)
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    resp = await svc.detect(pr.ref)

    # 无高危风险，第二层不触发
    assert deepseek.reason_called is False
    assert resp.usage.total_tokens == 150
    assert len(resp.risks) == 1


async def test_review_bad_json_keeps_v3_result():
    pr = _sample_pr()
    deepseek = _FakeDeepSeek(_HIGH_RISK, reason_content="R1 没有返回 JSON")
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    resp = await svc.detect(pr.ref)

    # R1 输出无法解析时，保留 V3 的高危风险不动
    assert deepseek.reason_called is True
    assert len(resp.risks) == 1
    assert resp.risks[0].severity == "high"
    assert resp.risks[0].confidence == 0.8


async def test_review_prompt_includes_high_risks_only():
    pr = _sample_pr()
    content = (
        '{"risks": ['
        '{"file": "auth.py", "line": 12, "severity": "high", "category": "security", '
        '"title": "SQL 注入", "detail": "拼接输入"}, '
        '{"file": "auth.py", "line": 3, "severity": "low", "category": "maintainability", '
        '"title": "命名不清", "detail": "变量名"}'
        ']}'
    )
    deepseek = _FakeDeepSeek(content, reason_content='{"reviews": []}')
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek)

    await svc.detect(pr.ref)

    review_prompt = deepseek.reason_messages[1].content
    assert "SQL 注入" in review_prompt
    # 非高危风险不进入复查 prompt
    assert "命名不清" not in review_prompt


# ---- 缓存：以 head_sha 为版本标识 ----


async def test_detect_second_call_hits_cache(tmp_path):
    pr = _sample_pr()
    cache = AnalysisCache(str(tmp_path / "c.db"))
    content = (
        '{"risks": [{"file": "auth.py", "line": 12, "severity": "medium", '
        '"category": "security", "title": "SQL 注入", "confidence": 0.9}]}'
    )
    deepseek = _FakeDeepSeek(content)
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek, cache=cache)

    first = await svc.detect(pr.ref)
    second = await svc.detect(pr.ref)

    # 第二次命中缓存，不再调用模型
    assert deepseek.chat_calls == 1
    assert first.cached is False
    assert second.cached is True
    assert len(second.risks) == 1
    assert second.risks[0].title == "SQL 注入"


async def test_detect_cache_miss_on_head_sha_change(tmp_path):
    pr = _sample_pr()
    cache = AnalysisCache(str(tmp_path / "c.db"))
    deepseek = _FakeDeepSeek('{"risks": []}')
    svc = RiskService(github=_FakeGitHub(pr), deepseek=deepseek, cache=cache)

    await svc.detect(pr.ref)
    pr.head_sha = "h2"
    resp = await svc.detect(pr.ref)

    # head_sha 变化后旧缓存不命中，重新分析
    assert deepseek.chat_calls == 2
    assert resp.cached is False


