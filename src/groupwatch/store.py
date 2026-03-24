from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import ErrorRecord, Post

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    group_id TEXT NOT NULL,
    author TEXT,
    text TEXT,
    url TEXT,
    collected_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS errors (
    at TEXT NOT NULL,
    group_id TEXT NOT NULL,
    account TEXT,
    kind TEXT NOT NULL,
    detail TEXT
);
"""


class Store:
    def __init__(self, path: Path | str) -> None:
        self._db = sqlite3.connect(str(path))
        self._db.executescript(SCHEMA)

    def remember(self, posts: Iterable[Post]) -> list[Post]:
        fresh = []
        with self._db:
            for p in posts:
                cur = self._db.execute(
                    "INSERT OR IGNORE INTO posts VALUES (?, ?, ?, ?, ?, ?)",
                    (p.post_id, p.group_id, p.author, p.text, p.url, p.collected_at.isoformat()),
                )
                if cur.rowcount:
                    fresh.append(p)
        return fresh

    def log_error(self, error: ErrorRecord) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO errors VALUES (?, ?, ?, ?, ?)",
                (error.at.isoformat(), error.group_id, error.account, error.kind, error.detail),
            )

    def count_posts(self) -> int:
        return self._db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    def close(self) -> None:
        self._db.close()
