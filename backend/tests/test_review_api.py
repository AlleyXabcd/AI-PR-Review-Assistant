import pytest
from fastapi.testclient import TestClient

import app.api.review as review_module
from app.main import app
from app.models.llm import TokenUsage
from app.models.review import PRSummary, SummaryResponse


class _FakeService:
    async def summarize(self, ref):
        return SummaryResponse(
            title="Add caching",
            author="bob",
            state="open",
            base_branch="main",
            head_branch="feat-cache",
            html_url="https://github.com/o/r/pull/1",
            additions=20,
            deletions=3,
            changed_files=2,
            files=[],
            commits=[],
            summary=PRSummary(
                overview="引入缓存层", key_changes=["新增 cache.py"], impact="关注失效"
            ),
            model="deepseek-chat",
            usage=TokenUsage(total_tokens=150),
        )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(review_module, "SummaryService", lambda: _FakeService())
    return TestClient(app)


def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_summary_ok(client):
    r = client.post("/review/summary", json={"pr_url": "o/r#1"})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Add caching"
    assert data["summary"]["overview"] == "引入缓存层"
    assert data["summary"]["key_changes"] == ["新增 cache.py"]


def test_summary_bad_url(client):
    r = client.post("/review/summary", json={"pr_url": "not-a-url"})
    assert r.status_code == 400
