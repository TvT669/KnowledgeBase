from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import DB_PATH, ensure_db


def main() -> None:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        print("Testing FTS5 search for '幂等':")
        cur.execute(
            """
            SELECT rowid, content FROM messages_fts
            WHERE messages_fts MATCH '幂等'
            LIMIT 2
            """
        )
        results = cur.fetchall()
        if results:
            for row in results:
                msg_preview = row[1][:70] + "..." if len(row[1]) > 70 else row[1]
                print(f"  [{row[0]}] {msg_preview}")
            return

        print("  (no results in FTS, testing LIKE fallback...)")
        cur.execute(
            """
            SELECT id, role, content FROM messages
            WHERE content LIKE '%幂等%'
            LIMIT 2
            """
        )
        for row in cur.fetchall():
            msg_preview = row[2][:70] + "..." if len(row[2]) > 70 else row[2]
            print(f"  [{row[0]}] {row[1]}: {msg_preview}")


if __name__ == "__main__":
    main()
