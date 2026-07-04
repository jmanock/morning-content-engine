from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from content_engine.models import GeneratedPost, QueuedContent, Signal


DEFAULT_DB_PATH = Path("data/content_archive.sqlite3")


class ContentArchive:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connection() as conn:
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY,
                    source_project TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    brand TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    description TEXT NOT NULL,
                    url TEXT NOT NULL,
                    affiliate_url TEXT NOT NULL,
                    category TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    expiration TEXT NOT NULL,
                    image_prompt TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_brand ON signals(brand)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS content_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    signal_id TEXT NOT NULL,
                    brand TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    rank_score INTEGER NOT NULL,
                    scheduled_time TEXT NOT NULL,
                    duplicate_risk TEXT NOT NULL,
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(date, signal_id, platform)
                )
                """
            )
            self._ensure_column(conn, "content_queue", "reason", "TEXT NOT NULL DEFAULT ''")

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def existing_content_keys(self) -> set[str]:
        with self._connection() as conn:
            rows = conn.execute("SELECT content_hash FROM posts").fetchall()
        return {row[0] for row in rows}

    def save_posts(self, posts: list[GeneratedPost]) -> int:
        saved = 0
        with self._connection() as conn:
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
        with self._connection() as conn:
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
        with self._connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            average = conn.execute("SELECT AVG(score) FROM posts").fetchone()[0] or 0
            brands = conn.execute("SELECT COUNT(DISTINCT brand) FROM posts").fetchone()[0]
        return {"total_posts": total, "average_score": round(float(average), 2), "brands": brands}

    def save_signals(self, signals: list[Signal]) -> int:
        saved = 0
        with self._connection() as conn:
            for signal in signals:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO signals
                    (id, source_project, source_type, brand, title, summary, description, url, affiliate_url,
                     category, tags, priority, confidence, expiration, image_prompt, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        signal.id,
                        signal.source_project,
                        signal.source_type,
                        signal.brand,
                        signal.title,
                        signal.summary,
                        signal.description,
                        signal.url,
                        signal.affiliate_url,
                        signal.category,
                        json.dumps(signal.tags),
                        signal.priority,
                        signal.confidence,
                        signal.expiration,
                        signal.image_prompt,
                        json.dumps(signal.metadata),
                        signal.created_at,
                    ),
                )
                saved += cursor.rowcount
        return saved

    def existing_signal_ids(self) -> set[str]:
        with self._connection() as conn:
            rows = conn.execute("SELECT id FROM signals").fetchall()
        return {row[0] for row in rows}

    def recent_signals(
        self,
        limit: int = 50,
        brand_filter: str | None = None,
        today_only: bool = False,
        high_priority: bool = False,
    ) -> list[Signal]:
        where: list[str] = []
        params: list[object] = []
        if brand_filter:
            normalized = brand_filter.replace("-", " ").replace("_", " ").lower()
            where.append("(lower(brand) = ? OR lower(source_project) = ?)")
            params.extend([normalized, normalized])
        if today_only:
            where.append("date(imported_at) = date('now')")
        if high_priority:
            where.append("priority >= 8")
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, source_project, source_type, brand, title, summary, description, url, affiliate_url,
                       category, tags, priority, confidence, expiration, image_prompt, metadata, created_at
                FROM signals
                {where_sql}
                ORDER BY imported_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [self._signal_from_row(row) for row in rows]

    def signal_duplicate_keys(self, days: int = 14, exclude_date: str | None = None) -> set[str]:
        with self._connection() as conn:
            exclude_sql = "AND q.date != ?" if exclude_date else ""
            params: tuple[object, ...] = (f"-{days} days", exclude_date) if exclude_date else (f"-{days} days",)
            rows = conn.execute(
                f"""
                SELECT DISTINCT q.signal_id, lower(s.title), lower(s.url)
                FROM content_queue q
                JOIN signals s ON s.id = q.signal_id
                WHERE q.date >= date('now', ?)
                {exclude_sql}
                """,
                params,
            ).fetchall()
            content_rows = conn.execute(
                """
                SELECT DISTINCT content_hash FROM posts
                WHERE date >= date('now', ?)
                """,
                (f"-{days} days",),
            ).fetchall()
        keys: set[str] = set()
        for row in rows:
            keys.update(value for value in row if value)
        keys.update(row[0] for row in content_rows)
        return keys

    def save_queue(self, queue: list[QueuedContent]) -> int:
        saved = 0
        with self._connection() as conn:
            for item in queue:
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO content_queue
                    (date, signal_id, brand, platform, content_type, rank_score, scheduled_time, duplicate_risk, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.date,
                        item.signal.id,
                        item.brand,
                        item.platform,
                        item.content_type,
                        item.rank_score,
                        item.scheduled_time,
                        item.duplicate_risk,
                        item.reason,
                    ),
                )
                saved += cursor.rowcount
        return saved

    def replace_queue_for_date(self, queue_date: str, queue: list[QueuedContent]) -> int:
        with self._connection() as conn:
            conn.execute("DELETE FROM content_queue WHERE date = ?", (queue_date,))
        return self.save_queue(queue)

    def queue_for_date(self, queue_date: str) -> list[QueuedContent]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT q.date, q.brand, q.platform, q.content_type, q.rank_score, q.scheduled_time, q.duplicate_risk, q.reason,
                       s.id, s.source_project, s.source_type, s.brand, s.title, s.summary, s.description, s.url,
                       s.affiliate_url, s.category, s.tags, s.priority, s.confidence, s.expiration, s.image_prompt,
                       s.metadata, s.created_at
                FROM content_queue q
                JOIN signals s ON s.id = q.signal_id
                WHERE q.date = ?
                ORDER BY q.id ASC
                """,
                (queue_date,),
            ).fetchall()
        return [self._queue_from_row(row) for row in rows]

    def signal_stats(self) -> dict[str, int | float]:
        with self._connection() as conn:
            total_signals = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            queued = conn.execute("SELECT COUNT(*) FROM content_queue").fetchone()[0]
            avg_confidence = conn.execute("SELECT AVG(confidence) FROM signals").fetchone()[0] or 0
            brands = conn.execute("SELECT COUNT(DISTINCT brand) FROM signals").fetchone()[0]
        return {
            "total_signals": total_signals,
            "queued_items": queued,
            "average_confidence": round(float(avg_confidence), 3),
            "signal_brands": brands,
        }

    def _signal_from_row(self, row: tuple) -> Signal:
        return Signal.from_dict(
            {
                "id": row[0],
                "source_project": row[1],
                "source_type": row[2],
                "brand": row[3],
                "title": row[4],
                "summary": row[5],
                "description": row[6],
                "url": row[7],
                "affiliate_url": row[8],
                "category": row[9],
                "tags": json.loads(row[10]),
                "priority": row[11],
                "confidence": row[12],
                "expiration": row[13],
                "image_prompt": row[14],
                "metadata": json.loads(row[15]),
                "created_at": row[16],
            }
        )

    def _queue_from_row(self, row: tuple) -> QueuedContent:
        signal = Signal.from_dict(
            {
                "id": row[8],
                "source_project": row[9],
                "source_type": row[10],
                "brand": row[11],
                "title": row[12],
                "summary": row[13],
                "description": row[14],
                "url": row[15],
                "affiliate_url": row[16],
                "category": row[17],
                "tags": json.loads(row[18]),
                "priority": row[19],
                "confidence": row[20],
                "expiration": row[21],
                "image_prompt": row[22],
                "metadata": json.loads(row[23]),
                "created_at": row[24],
            }
        )
        return QueuedContent(
            date=row[0],
            brand=row[1],
            platform=row[2],
            content_type=row[3],
            rank_score=row[4],
            scheduled_time=row[5],
            duplicate_risk=row[6],
            reason=row[7] or self._default_queue_reason(signal, row[2], row[4], row[6]),
            signal=signal,
        )

    def _default_queue_reason(self, signal: Signal, platform: str, rank_score: int, duplicate_risk: str) -> str:
        return (
            f"priority {signal.priority}/10; confidence {round(signal.confidence * 100)}%; "
            f"rank {rank_score}/100; {platform} fit; duplicate risk {duplicate_risk}"
        )
