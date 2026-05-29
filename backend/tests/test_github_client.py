import httpx
import pytest
import respx

from app.core.config import Settings
from app.models.github import PRRef
from app.services.github_client import GitHubClient, GitHubError

API = "https://api.github.com"


def _settings() -> Settings:
    return Settings(github_token="", github_api_base=API, http_timeout=5.0)


@pytest.fixture
def ref() -> PRRef:
    return PRRef(owner="octo", repo="demo", number=1)


@respx.mock
async def test_fetch_pull_request_ok(ref):
    respx.get(f"{API}/repos/octo/demo/pulls/1").mock(
        return_value=httpx.Response(
            200,
            json={
                "title": "Add feature",
                "body": "desc",
                "user": {"login": "alice"},
                "state": "open",
                "base": {"ref": "main", "sha": "base123"},
                "head": {"ref": "feat", "sha": "head456"},
                "additions": 10,
                "deletions": 2,
                "changed_files": 1,
                "html_url": "https://github.com/octo/demo/pull/1",
            },
        )
    )
    respx.get(f"{API}/repos/octo/demo/pulls/1/files").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "filename": "src/app.py",
                    "status": "modified",
                    "additions": 10,
                    "deletions": 2,
                    "changes": 12,
                    "patch": "@@ -1 +1 @@\n-old\n+new",
                }
            ],
        )
    )
    respx.get(f"{API}/repos/octo/demo/pulls/1/commits").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "sha": "abc1234567",
                    "commit": {
                        "message": "Add feature\n\ndetails",
                        "author": {"name": "alice", "date": "2026-05-29T00:00:00Z"},
                    },
                }
            ],
        )
    )

    pr = await GitHubClient(_settings()).fetch_pull_request(ref)

    assert pr.title == "Add feature"
    assert pr.author == "alice"
    assert pr.base_branch == "main"
    assert pr.head_sha == "head456"
    assert len(pr.files) == 1
    assert pr.files[0].filename == "src/app.py"
    assert pr.files[0].patch.startswith("@@")
    assert len(pr.commits) == 1
    assert pr.commits[0].sha == "abc1234567"


@respx.mock
async def test_fetch_pull_request_404(ref):
    respx.get(f"{API}/repos/octo/demo/pulls/1").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"})
    )
    with pytest.raises(GitHubError):
        await GitHubClient(_settings()).fetch_pull_request(ref)
