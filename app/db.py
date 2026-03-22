from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "knowledge.db"
DB_PATH = Path(os.getenv("KNOWLEDGE_DB_PATH", str(DEFAULT_DB_PATH))).expanduser()
DATA_DIR = DB_PATH.parent


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _open_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                content_hash TEXT NOT NULL UNIQUE,
                summary TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                summary,
                source,
                session_id,
                content='messages',
                content_rowid='id'
            )
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content, summary, source, session_id)
                VALUES (new.id, new.content, coalesce(new.summary, ''), new.source, coalesce(new.session_id, ''));
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                UPDATE messages_fts
                SET content = new.content,
                    summary = coalesce(new.summary, ''),
                    source = new.source,
                    session_id = coalesce(new.session_id, '')
                WHERE rowid = new.id;
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                DELETE FROM messages_fts WHERE rowid = old.id;
            END;
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                problem TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                solution TEXT NOT NULL,
                key_takeaways TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                source_type TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS note_sources (
                note_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (note_id, message_id),
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
                title,
                problem,
                root_cause,
                solution,
                key_takeaways,
                content='notes',
                content_rowid='id'
            )
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
                INSERT INTO notes_fts(rowid, title, problem, root_cause, solution, key_takeaways)
                VALUES (
                    new.id,
                    new.title,
                    new.problem,
                    new.root_cause,
                    new.solution,
                    new.key_takeaways
                );
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
                UPDATE notes_fts
                SET title = new.title,
                    problem = new.problem,
                    root_cause = new.root_cause,
                    solution = new.solution,
                    key_takeaways = new.key_takeaways
                WHERE rowid = new.id;
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
                DELETE FROM notes_fts WHERE rowid = old.id;
            END;
            """
        )


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    ensure_db()
    conn = _open_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
