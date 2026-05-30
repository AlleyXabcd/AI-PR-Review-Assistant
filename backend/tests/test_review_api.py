import pytest
from fastapi.testclient import TestClient

import app.api.review as review_module
from app.main import app
from app.models.llm import TokenUsage
from app.models.review import PRSummary, RiskItem, RisksResponse, SummaryResponse


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


class _FakeRiskService:
    async def detect(self, ref):
        return RisksResponse(
            title="Add login",
            author="bob",
            state="open",
            base_branch="main",
            head_branch="feat-login",
            html_url="https://github.com/o/r/pull/1",
            additions=20,
            deletions=3,
            changed_files=1,
            files=[],
            risks=[
                RiskItem(
                    file="auth.py",
                    line=12,
                    severity="high",
                    category="security",
                    title="SQL 注入",
                    detail="拼接用户输入",
                    suggestion="使用参数化查询",
                    confidence=0.9,
                )
            ],
            model="deepseek-chat",
            usage=TokenUsage(total_tokens=150),
        )


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(review_module, "SummaryService", lambda: _FakeService())
    monkeypatch.setattr(review_module, "RiskService", lambda: _FakeRiskService())
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


def test_risks_ok(client):
    r = client.post("/review/risks", json={"pr_url": "o/r#1"})
    assert r.status_code == 200
    data = r.json()
    assert data["title"] == "Add login"
    assert len(data["risks"]) == 1
    risk = data["risks"][0]
    assert risk["file"] == "auth.py"
    assert risk["severity"] == "high"
    assert risk["category"] == "security"
    assert risk["confidence"] == 0.9


def test_risks_bad_url(client):
    r = client.post("/review/risks", json={"pr_url": "not-a-url"})
    assert r.status_code == 400
