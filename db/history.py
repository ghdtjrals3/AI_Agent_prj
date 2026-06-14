import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "reviews.db")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                pr_url     TEXT    NOT NULL,
                created_at TEXT    NOT NULL,
                extensions TEXT    DEFAULT '',
                result     TEXT    NOT NULL
            )
        """)
        conn.commit()


def save_review(pr_url: str, result: str, extensions: str = "") -> int:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO reviews (pr_url, created_at, extensions, result) VALUES (?, ?, ?, ?)",
            (pr_url, created_at, extensions, result),
        )
        conn.commit()
        return cur.lastrowid


def get_history(limit: int = 50, row_id: int | None = None) -> list[tuple]:
    """
    row_id 지정 시 해당 행 전체 반환 (result 포함).
    미지정 시 최근 limit개의 (id, pr_url, created_at, extensions, preview) 반환.
    """
    with _connect() as conn:
        if row_id is not None:
            rows = conn.execute(
                "SELECT id, pr_url, created_at, extensions, result FROM reviews WHERE id = ?",
                (row_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, pr_url, created_at, extensions,
                       substr(result, 1, 200) AS preview
                FROM reviews
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return rows


def delete_review(row_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM reviews WHERE id = ?", (row_id,))
        conn.commit()
