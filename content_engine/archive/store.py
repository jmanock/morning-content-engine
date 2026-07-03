from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from content_engine.models import GeneratedPost


DEFAULT_DB_PATH = Path("data/content_archive.sqlite3")


class ContentArchive:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    brand TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    content TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE,
                    hashtags TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    template_used TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def existing_content_keys(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT content_hash FROM posts").fetchall()
        return {row[0] for row in rows}

    def save_posts(self, posts: list[GeneratedPost]) -> int:
        saved = 0
        with self._connect() as conn:
            for post in posts:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO posts
                    (date, brand, platform, content, content_hash, hashtags, score, template_used, content_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        post.date,
                        post.brand,
                        post.platform,
                        post.content,
                        post.archive_key(),
                        json.dumps(post.hashtags),
                        post.score,
                        post.template_used,
                        post.content_type,
                    ),
                )
                saved += cursor.rowcount
        return saved

    def history(self, limit: int = 20) -> list[dict[str, str | int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date, brand, platform, content_type, score, template_used
                FROM posts
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "date": row[0],
                "brand": row[1],
                "platform": row[2],
                "content_type": row[3],
                "score": row[4],
                "template_used": row[5],
            }
            for row in rows
        ]

    def stats(self) -> dict[str, int | float]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            average = conn.execute("SELECT AVG(score) FROM posts").fetchone()[0] or 0
            brands = conn.execute("SELECT COUNT(DISTINCT brand) FROM posts").fetchone()[0]
        return {"total_posts": total, "average_score": round(float(average), 2), "brands": brands}

