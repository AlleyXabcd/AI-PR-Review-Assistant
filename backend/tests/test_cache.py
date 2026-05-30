from app.models.github import PRRef
from app.services.cache import AnalysisCache


def _cache(tmp_path) -> AnalysisCache:
    return AnalysisCache(str(tmp_path / "cache.db"))


def test_set_then_get_roundtrips(tmp_path):
    cache = _cache(tmp_path)
    cache.set("k1", {"a": 1, "msg": "中文"})

    assert cache.get("k1") == {"a": 1, "msg": "中文"}


def test_get_missing_returns_none(tmp_path):
    cache = _cache(tmp_path)

    assert cache.get("nope") is None


def test_set_overwrites_existing(tmp_path):
    cache = _cache(tmp_path)
    cache.set("k1", {"v": 1})
    cache.set("k1", {"v": 2})

    assert cache.get("k1") == {"v": 2}


def test_make_key_includes_sha_for_versioning():
    ref = PRRef(owner="o", repo="r", number=7)
    k1 = AnalysisCache.make_key("risks", ref, "sha-aaa")
    k2 = AnalysisCache.make_key("risks", ref, "sha-bbb")

    assert k1 == "risks:o/r#7@sha-aaa"
    # head_sha 不同 → key 不同 → 旧缓存自然不命中
    assert k1 != k2


def test_make_key_separates_kinds():
    ref = PRRef(owner="o", repo="r", number=7)
    summary_key = AnalysisCache.make_key("summary", ref, "s1")
    risks_key = AnalysisCache.make_key("risks", ref, "s1")

    assert summary_key != risks_key


def test_different_sha_does_not_hit(tmp_path):
    cache = _cache(tmp_path)
    ref = PRRef(owner="o", repo="r", number=7)
    cache.set(AnalysisCache.make_key("risks", ref, "old"), {"v": "old"})

    assert cache.get(AnalysisCache.make_key("risks", ref, "new")) is None
