"""分析结果缓存：以 (kind + PR + head_sha) 为 key 缓存 summary / risks 分析结果。

用 head_sha 作为版本标识：PR 代码一旦变化 head_sha 即变，旧缓存自然不再命中，
无需显式失效。基于标准库 sqlite3，零额外依赖。
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from functools import lru_cache

from app.core.config import get_settings
from app.models.github import PRRef

logger = logging.getLogger(__name__)


class AnalysisCache:
    """分析结果的 SQLite 缓存。

    线程安全：每次操作使用独立短连接（sqlite3 连接默认不可跨线程共享），
    用一把锁串行化写入，避免并发建表/写入冲突。
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=5.0)

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    @staticmethod
    def make_key(kind: str, ref: PRRef, head_sha: str) -> str:
        """构造缓存 key：分析类型 + 仓库 + PR 号 + head sha。"""
        return f"{kind}:{ref.owner}/{ref.repo}#{ref.number}@{head_sha}"

    def get(self, key: str) -> dict | None:
        """命中返回缓存的 dict，未命中或解析失败返回 None。"""
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT value FROM analysis_cache WHERE key = ?", (key,)
                ).fetchone()
        except sqlite3.Error as exc:
            logger.warning("缓存读取失败，跳过缓存：%s", exc)
            return None

        if row is None:
            return None
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            logger.warning("缓存值解析失败，视为未命中：%s", key)
            return None

    def set(self, key: str, value: dict) -> None:
        """写入/覆盖缓存。写入失败仅记录日志，不影响主流程。"""
        try:
            payload = json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            logger.warning("缓存值序列化失败，跳过写入：%s", exc)
            return

        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO analysis_cache (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        created_at = datetime('now')
                    """,
                    (key, payload),
                )
        except sqlite3.Error as exc:
            logger.warning("缓存写入失败，跳过：%s", exc)


@lru_cache
def get_cache() -> AnalysisCache | None:
    """按配置返回单例缓存；cache_enabled=False 时返回 None（不缓存）。"""
    settings = get_settings()
    if not settings.cache_enabled:
        return None
    return AnalysisCache(settings.cache_db_path)
