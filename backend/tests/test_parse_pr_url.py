import pytest

from app.services.github_client import GitHubError, parse_pr_url


@pytest.mark.parametrize(
    "raw,owner,repo,number",
    [
        ("https://github.com/openai/openai-python/pull/123", "openai", "openai-python", 123),
        ("http://github.com/a/b/pull/7", "a", "b", 7),
        ("github.com/a/b/pull/42", "a", "b", 42),
        ("git@github.com:a/b/pull/9", "a", "b", 9),
        ("owner/repo#15", "owner", "repo", 15),
        ("owner/repo/pull/16", "owner", "repo", 16),
        ("https://github.com/a/b.git/pull/3", "a", "b", 3),
        ("  https://github.com/a/b/pull/123  ", "a", "b", 123),
    ],
)
def test_parse_pr_url_ok(raw, owner, repo, number):
    ref = parse_pr_url(raw)
    assert ref.owner == owner
    assert ref.repo == repo
    assert ref.number == number


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "https://gitlab.com/a/b/pull/1",
        "not a url",
        "https://github.com/a/b/issues/1",
        "owner/repo",
    ],
)
def test_parse_pr_url_invalid(raw):
    with pytest.raises(GitHubError):
        parse_pr_url(raw)


def test_pr_ref_str_and_fullname():
    ref = parse_pr_url("owner/repo#15")
    assert ref.full_name == "owner/repo"
    assert str(ref) == "owner/repo#15"
