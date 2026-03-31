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
            CREATE INDEX IF NOT EXISTS messages_source_session_latest_idx
            ON messages(source, session_id, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS messages_session_latest_idx
            ON messages(session_id, id DESC)
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
            CREATE INDEX IF NOT EXISTS note_sources_note_sort_idx
            ON note_sources(note_id, sort_order)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS note_tags (
                note_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (note_id, tag),
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS note_tags_tag_note_idx
            ON note_tags(tag, note_id)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS note_append_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER NOT NULL,
                source TEXT,
                session_id TEXT,
                origin_label TEXT NOT NULL,
                source_count_added INTEGER NOT NULL DEFAULT 0,
                summary_text TEXT NOT NULL DEFAULT '',
                changed_sections_json TEXT NOT NULL DEFAULT '[]',
                added_tags_json TEXT NOT NULL DEFAULT '[]',
                section_updates_json TEXT NOT NULL DEFAULT '[]',
                added_message_ids_json TEXT NOT NULL DEFAULT '[]',
                previous_tags_json TEXT NOT NULL DEFAULT '[]',
                previous_status TEXT NOT NULL DEFAULT 'draft',
                previous_source_type TEXT NOT NULL DEFAULT 'manual',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS note_append_events_note_created_idx
            ON note_append_events(note_id, created_at DESC, id DESC)
            """
        )
        note_append_events_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(note_append_events)").fetchall()
        }
        if "section_updates_json" not in note_append_events_columns:
            conn.execute(
                """
                ALTER TABLE note_append_events
                ADD COLUMN section_updates_json TEXT NOT NULL DEFAULT '[]'
                """
            )
        if "added_message_ids_json" not in note_append_events_columns:
            conn.execute(
                """
                ALTER TABLE note_append_events
                ADD COLUMN added_message_ids_json TEXT NOT NULL DEFAULT '[]'
                """
            )
        if "previous_tags_json" not in note_append_events_columns:
            conn.execute(
                """
                ALTER TABLE note_append_events
                ADD COLUMN previous_tags_json TEXT NOT NULL DEFAULT '[]'
                """
            )
        if "previous_status" not in note_append_events_columns:
            conn.execute(
                """
                ALTER TABLE note_append_events
                ADD COLUMN previous_status TEXT NOT NULL DEFAULT 'draft'
                """
            )
        if "previous_source_type" not in note_append_events_columns:
            conn.execute(
                """
                ALTER TABLE note_append_events
                ADD COLUMN previous_source_type TEXT NOT NULL DEFAULT 'manual'
                """
            )
        for column in (
            "changed_sections_json",
            "added_tags_json",
            "section_updates_json",
            "added_message_ids_json",
            "previous_tags_json",
        ):
            conn.execute(
                f"""
                UPDATE note_append_events
                SET {column} = '[]'
                WHERE {column} IS NULL OR TRIM({column}) = ''
                """
            )
        conn.execute(
            """
            UPDATE note_append_events
            SET summary_text = ''
            WHERE summary_text IS NULL
            """
        )
        conn.execute(
            """
            UPDATE note_append_events
            SET previous_status = 'draft'
            WHERE previous_status IS NULL OR TRIM(previous_status) = ''
            """
        )
        conn.execute(
            """
            UPDATE note_append_events
            SET previous_source_type = 'manual'
            WHERE previous_source_type IS NULL OR TRIM(previous_source_type) = ''
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_insights (
                source TEXT NOT NULL,
                session_id TEXT NOT NULL,
                latest_message_id INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                topic_title TEXT NOT NULL,
                topic_excerpt TEXT NOT NULL,
                tags_json TEXT NOT NULL DEFAULT '[]',
                length_label TEXT NOT NULL,
                priority_score INTEGER NOT NULL DEFAULT 0,
                priority_label TEXT NOT NULL,
                priority_reason TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (source, session_id),
                FOREIGN KEY (latest_message_id) REFERENCES messages(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_queue (
                source TEXT NOT NULL,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                ai_title TEXT NOT NULL,
                ai_excerpt TEXT NOT NULL DEFAULT '',
                ai_tags_json TEXT NOT NULL DEFAULT '[]',
                ai_priority TEXT NOT NULL DEFAULT '待判断',
                ai_reason TEXT NOT NULL DEFAULT '',
                ai_confidence REAL NOT NULL DEFAULT 0,
                user_title TEXT,
                user_tags_json TEXT NOT NULL DEFAULT '[]',
                user_priority TEXT,
                note_id INTEGER,
                message_count INTEGER NOT NULL DEFAULT 0,
                latest_message_id INTEGER NOT NULL,
                length_label TEXT NOT NULL DEFAULT '',
                first_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_seen_at TEXT NOT NULL DEFAULT (datetime('now')),
                last_reviewed_at TEXT,
                snooze_until TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (source, session_id),
                FOREIGN KEY (latest_message_id) REFERENCES messages(id) ON DELETE CASCADE,
                FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS session_queue_status_last_seen_idx
            ON session_queue(status, last_seen_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS session_queue_updated_latest_idx
            ON session_queue(updated_at DESC, latest_message_id DESC)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ide_sync_files (
                source TEXT NOT NULL,
                path TEXT NOT NULL,
                session_id TEXT NOT NULL DEFAULT '',
                file_size INTEGER NOT NULL DEFAULT 0,
                modified_at INTEGER NOT NULL DEFAULT 0,
                message_count INTEGER NOT NULL DEFAULT 0,
                last_synced_at TEXT NOT NULL DEFAULT (datetime('now')),
                PRIMARY KEY (source, path)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS ide_sync_files_source_session_idx
            ON ide_sync_files(source, session_id)
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
