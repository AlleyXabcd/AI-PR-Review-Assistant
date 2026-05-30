import asyncio

import pytest
from fastapi.testclient import TestClient

import app.api.review as review_module
from app.main import app
from app.models.github import PRRef
from app.models.llm import TokenUsage
from app.models.review import PRSummary, RiskItem, RisksResponse, SummaryResponse
from app.services.review_stream import StreamEvent, format_sse, stream_analysis
from app.services.summary_service import SummaryStreamChunk

_REF = PRRef(owner="o", repo="r", number=1)


def _summary() -> SummaryResponse:
    return SummaryResponse(
        title="t",
        state="open",
        base_branch="main",
        head_branch="feat",
        summary=PRSummary(overview="概述", key_changes=[], impact=""),
        model="deepseek-chat",
        usage=TokenUsage(total_tokens=150),
    )


def _risks() -> RisksResponse:
    return RisksResponse(
        title="t",
        state="open",
        base_branch="main",
        head_branch="feat",
        risks=[RiskItem(file="a.py", title="风险")],
        model="deepseek-chat",
        usage=TokenUsage(total_tokens=150),
    )


class _FakeSummary:
    def __init__(self, deltas: list[str] | None = None, exc: Exception | None = None):
        self._deltas = deltas if deltas is not None else ["概", "述"]
        self._exc = exc

    async def summarize_stream(self, ref):
        if self._exc:
            raise self._exc
        for d in self._deltas:
            yield SummaryStreamChunk(delta=d)
        yield SummaryStreamChunk(result=_summary())


class _FakeRisk:
    def __init__(self, delay: float = 0.0, exc: Exception | None = None):
        self._delay = delay
        self._exc = exc

    async def detect(self, ref):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc:
            raise self._exc
        return _risks()


async def _collect(gen) -> list[StreamEvent]:
    return [ev async for ev in gen]


def test_format_sse_frame():
    frame = format_sse(StreamEvent("summary", {"a": 1}))
    assert frame == 'event: summary\ndata: {"a": 1}\n\n'


async def test_event_order_deltas_then_summary_then_risks():
    events = await _collect(
        stream_analysis(
            _REF,
            summary_service=_FakeSummary(deltas=["概", "述"]),
            risk_service=_FakeRisk(),
        )
    )
    names = [e.event for e in events]
    # stage → 逐字 summary_delta → summary → stage(风险) → risks → done
    assert names == [
        "stage",
        "summary_delta",
        "summary_delta",
        "summary",
        "stage",
        "risks",
        "done",
    ]
    deltas = [e.data["text"] for e in events if e.event == "summary_delta"]
    assert "".join(deltas) == "概述"


async def test_summary_payload_is_serialized():
    events = await _collect(
        stream_analysis(
            _REF, summary_service=_FakeSummary(), risk_service=_FakeRisk()
        )
    )
    summary_ev = next(e for e in events if e.event == "summary")
    assert summary_ev.data["summary"]["overview"] == "概述"
    risks_ev = next(e for e in events if e.event == "risks")
    assert risks_ev.data["risks"][0]["file"] == "a.py"


async def test_error_event_when_summary_fails():
    from app.services.deepseek_client import DeepSeekError

    events = await _collect(
        stream_analysis(
            _REF,
            summary_service=_FakeSummary(exc=DeepSeekError("boom")),
            risk_service=_FakeRisk(delay=0.05),
        )
    )
    names = [e.event for e in events]
    # 总结出错后产出 error 并结束，不再有 risks / done
    assert "error" in names
    assert "done" not in names
    assert "risks" not in names
    err = next(e for e in events if e.event == "error")
    assert "模型调用失败" in err.data["message"]


async def test_error_event_when_risk_fails():
    from app.services.github_client import GitHubError

    events = await _collect(
        stream_analysis(
            _REF,
            summary_service=_FakeSummary(),
            risk_service=_FakeRisk(exc=GitHubError("404")),
        )
    )
    names = [e.event for e in events]
    # 总结正常产出，风险失败 → error，无 done
    assert "summary" in names
    assert "error" in names
    assert "done" not in names


@pytest.fixture
def client(monkeypatch):
    async def fake_stream(ref, *, cache=None):
        yield StreamEvent("stage", {"message": "x"})
        yield StreamEvent("summary_delta", {"text": "概"})
        yield StreamEvent("summary", _summary().model_dump())
        yield StreamEvent("risks", _risks().model_dump())
        yield StreamEvent("done", {})

    monkeypatch.setattr(review_module, "stream_analysis", fake_stream)
    monkeypatch.setattr(review_module, "get_cache", lambda: None)
    return TestClient(app)


def test_stream_endpoint_content_type(client):
    with client.stream("GET", "/review/stream", params={"pr_url": "o/r#1"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = "".join(r.iter_text())
    assert "event: stage" in body
    assert "event: summary_delta" in body
    assert "event: summary" in body
    assert "event: risks" in body
    assert "event: done" in body


def test_stream_endpoint_bad_url_emits_error():
    # 不打桩 stream_analysis，验证 URL 解析失败走 error 事件而非 500
    c = TestClient(app)
    with c.stream("GET", "/review/stream", params={"pr_url": "not-a-url"}) as r:
        assert r.status_code == 200
        body = "".join(r.iter_text())
    assert "event: error" in body
