from __future__ import annotations

import asyncio
import threading
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from app.db import get_conn
from app.connectors.ide_collectors import (
    discover_vscode_chat_files,
    discover_windsurf_chat_files,
    load_messages_from_chat_file,
)
from app.services.ingest import insert_message
from app.services.inbox import refresh_inbox
from app.services.summarizer import summarize_text


_SYNC_MUTEX = threading.Lock()
_SYNC_THREAD: threading.Thread | None = None


def _empty_progress() -> dict[str, Any]:
    return {
        "total_files": 0,
        "processed_files": 0,
        "parsed_messages": 0,
        "inserted_messages": 0,
        "skipped_files": 0,
        "current_source": "",
        "current_file": "",
    }


_SYNC_STATE: dict[str, Any] = {
    "running": False,
    "last_started_at": "",
    "last_finished_at": "",
    "last_error": "",
    "last_result": None,
    "last_options": {
        "include_vscode": True,
        "include_windsurf": True,
    },
    "progress": _empty_progress(),
}


def _utc_now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _is_sync_running() -> bool:
    global _SYNC_THREAD
    if _SYNC_THREAD is not None and not _SYNC_THREAD.is_alive():
        _SYNC_THREAD = None
    return bool(_SYNC_THREAD is not None or _SYNC_STATE.get("running"))


def _prepare_sync_state(*, include_vscode: bool, include_windsurf: bool) -> None:
    _SYNC_STATE["running"] = True
    _SYNC_STATE["last_started_at"] = _utc_now()
    _SYNC_STATE["last_error"] = ""
    _SYNC_STATE["last_options"] = {
        "include_vscode": bool(include_vscode),
        "include_windsurf": bool(include_windsurf),
    }
    _SYNC_STATE["progress"] = _empty_progress()


def _finalize_sync_state() -> None:
    _SYNC_STATE["running"] = False
    progress = _SYNC_STATE.setdefault("progress", _empty_progress())
    progress["current_source"] = ""
    progress["current_file"] = ""


def get_ide_sync_state() -> dict[str, Any]:
    state = deepcopy(_SYNC_STATE)
    state["running"] = _is_sync_running()
    return state


async def run_ide_sync(
    *,
    include_vscode: bool = True,
    include_windsurf: bool = True,
    use_llm_summary: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    if _is_sync_running():
        raise RuntimeError("sync already in progress")
    if not include_vscode and not include_windsurf:
        raise ValueError("at least one sync source must be selected")

    _prepare_sync_state(include_vscode=include_vscode, include_windsurf=include_windsurf)

    try:
        stats = await asyncio.to_thread(
            _run_sync_job,
            include_vscode=include_vscode,
            include_windsurf=include_windsurf,
            use_llm_summary=use_llm_summary,
            home=home,
            refresh_after=False,
        )
        return stats
    except Exception as exc:
        _SYNC_STATE["last_finished_at"] = _utc_now()
        _SYNC_STATE["last_error"] = str(exc)
        raise
    finally:
        _finalize_sync_state()


def start_ide_sync(
    *,
    include_vscode: bool = True,
    include_windsurf: bool = True,
    use_llm_summary: bool = False,
    home: Path | None = None,
) -> dict[str, Any]:
    global _SYNC_THREAD

    if _is_sync_running():
        raise RuntimeError("sync already in progress")
    if not include_vscode and not include_windsurf:
        raise ValueError("at least one sync source must be selected")

    _prepare_sync_state(include_vscode=include_vscode, include_windsurf=include_windsurf)

    def _runner() -> None:
        global _SYNC_THREAD
        try:
            _run_sync_job(
                include_vscode=include_vscode,
                include_windsurf=include_windsurf,
                use_llm_summary=use_llm_summary,
                home=home,
                refresh_after=True,
            )
        except Exception as exc:
            _SYNC_STATE["last_finished_at"] = _utc_now()
            _SYNC_STATE["last_error"] = str(exc)
        finally:
            _finalize_sync_state()
            _SYNC_THREAD = None

    _SYNC_THREAD = threading.Thread(target=_runner, name="knowledgebase-ide-sync", daemon=True)
    _SYNC_THREAD.start()
    return get_ide_sync_state()


def _summarize_for_sync(content: str, *, use_llm_summary: bool) -> str:
    if not use_llm_summary:
        return content[:200]
    return asyncio.run(summarize_text(content))


def _file_signature(file_path: Path) -> tuple[int, int]:
    stat = file_path.stat()
    return int(stat.st_size), int(stat.st_mtime_ns)


def _load_known_file_cache() -> dict[tuple[str, str], dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT source, path, session_id, file_size, modified_at, message_count, last_synced_at
            FROM ide_sync_files
            """
        ).fetchall()
    return {(str(row["source"]), str(row["path"])): dict(row) for row in rows}


def _load_existing_session_ids(targets: list[tuple[str, list[Path]]]) -> dict[tuple[str, str], int]:
    sessions_by_source: dict[str, list[str]] = {}
    for source, files in targets:
        session_ids = [file_path.stem for file_path in files if file_path.stem]
        if session_ids:
            sessions_by_source[source] = list(dict.fromkeys(session_ids))

    if not sessions_by_source:
        return {}

    known: dict[tuple[str, str], int] = {}
    with get_conn() as conn:
        for source, session_ids in sessions_by_source.items():
            placeholders = ", ".join("?" for _ in session_ids)
            rows = conn.execute(
                f"""
                SELECT session_id, COUNT(*) AS message_count
                FROM messages
                WHERE source = ? AND session_id IN ({placeholders})
                GROUP BY session_id
                """,
                (source, *session_ids),
            ).fetchall()
            for row in rows:
                known[(source, str(row["session_id"]))] = int(row["message_count"] or 0)
    return known


def _save_file_cache_entry(
    *,
    source: str,
    path: Path,
    session_id: str,
    file_size: int,
    modified_at: int,
    message_count: int,
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO ide_sync_files(
                source,
                path,
                session_id,
                file_size,
                modified_at,
                message_count,
                last_synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, path) DO UPDATE SET
                session_id = excluded.session_id,
                file_size = excluded.file_size,
                modified_at = excluded.modified_at,
                message_count = excluded.message_count,
                last_synced_at = excluded.last_synced_at
            """,
            (
                source,
                str(path),
                session_id,
                int(file_size),
                int(modified_at),
                int(message_count),
                _utc_now(),
            ),
        )


def _run_sync_job(
    *,
    include_vscode: bool,
    include_windsurf: bool,
    use_llm_summary: bool,
    home: Path | None,
    refresh_after: bool,
) -> dict[str, Any]:
    with _SYNC_MUTEX:
        stats = _run_ide_sync_impl_sync(
            include_vscode=include_vscode,
            include_windsurf=include_windsurf,
            use_llm_summary=use_llm_summary,
            home=home,
        )
        if refresh_after:
            refresh_inbox(limit=120)
        _SYNC_STATE["last_finished_at"] = _utc_now()
        _SYNC_STATE["last_result"] = deepcopy(stats)
        return stats


def _run_ide_sync_impl_sync(
    *,
    include_vscode: bool,
    include_windsurf: bool,
    use_llm_summary: bool,
    home: Path | None = None,
) -> dict[str, Any]:
    import time

    started_at = time.time()
    resolved_home = home or Path.home()

    targets: list[tuple[str, list[Path]]] = []
    if include_vscode:
        targets.append(("vscode", discover_vscode_chat_files(resolved_home)))
    if include_windsurf:
        targets.append(("windsurf", discover_windsurf_chat_files(resolved_home)))

    progress = _SYNC_STATE.setdefault("progress", _empty_progress())
    progress.update(
        {
            "total_files": sum(len(files) for _, files in targets),
            "processed_files": 0,
            "parsed_messages": 0,
            "inserted_messages": 0,
            "skipped_files": 0,
            "current_source": "",
            "current_file": "",
        }
    )

    file_cache = _load_known_file_cache()
    known_sessions = _load_existing_session_ids(targets)

    stats: dict[str, Any] = {
        "files": 0,
        "parsed": 0,
        "inserted": 0,
        "deduped": 0,
        "skipped_files": 0,
        "elapsed_ms": 0,
        "selected_sources": {
            "include_vscode": bool(include_vscode),
            "include_windsurf": bool(include_windsurf),
        },
        "sources": {},
    }

    for source, files in targets:
        source_stats = {
            "files": len(files),
            "parsed": 0,
            "inserted": 0,
            "deduped": 0,
            "skipped_files": 0,
        }
        stats["files"] += len(files)

        for chat_file in files:
            progress["current_source"] = source
            progress["current_file"] = chat_file.name
            session_id = chat_file.stem
            cache_key = (source, str(chat_file))
            file_size, modified_at = _file_signature(chat_file)
            cached_file = file_cache.get(cache_key)
            known_message_count = int(known_sessions.get((source, session_id), 0))

            if cached_file and int(cached_file.get("file_size") or 0) == file_size and int(cached_file.get("modified_at") or 0) == modified_at:
                source_stats["skipped_files"] += 1
                stats["skipped_files"] += 1
                progress["skipped_files"] = stats["skipped_files"]
                progress["processed_files"] = int(progress["processed_files"]) + 1
                continue

            if not cached_file and known_message_count > 0:
                _save_file_cache_entry(
                    source=source,
                    path=chat_file,
                    session_id=session_id,
                    file_size=file_size,
                    modified_at=modified_at,
                    message_count=known_message_count,
                )
                file_cache[cache_key] = {
                    "source": source,
                    "path": str(chat_file),
                    "session_id": session_id,
                    "file_size": file_size,
                    "modified_at": modified_at,
                    "message_count": known_message_count,
                }
                source_stats["skipped_files"] += 1
                stats["skipped_files"] += 1
                progress["skipped_files"] = stats["skipped_files"]
                progress["processed_files"] = int(progress["processed_files"]) + 1
                continue

            messages = load_messages_from_chat_file(chat_file, source=source)
            source_stats["parsed"] += len(messages)
            stats["parsed"] += len(messages)
            progress["parsed_messages"] = stats["parsed"]

            for msg in messages:
                content = str(msg["content"])
                summary = _summarize_for_sync(content, use_llm_summary=use_llm_summary)
                inserted, _ = insert_message(
                    source=str(msg["source"]),
                    session_id=str(msg.get("session_id") or ""),
                    role=str(msg["role"]),
                    content=content,
                    summary=summary,
                )
                if inserted:
                    source_stats["inserted"] += 1
                    stats["inserted"] += 1
                    progress["inserted_messages"] = stats["inserted"]

            _save_file_cache_entry(
                source=source,
                path=chat_file,
                session_id=session_id,
                file_size=file_size,
                modified_at=modified_at,
                message_count=len(messages),
            )
            file_cache[cache_key] = {
                "source": source,
                "path": str(chat_file),
                "session_id": session_id,
                "file_size": file_size,
                "modified_at": modified_at,
                "message_count": len(messages),
            }
            progress["processed_files"] = int(progress["processed_files"]) + 1
        source_stats["deduped"] = source_stats["parsed"] - source_stats["inserted"]
        stats["sources"][source] = source_stats

    stats["deduped"] = stats["parsed"] - stats["inserted"]
    stats["elapsed_ms"] = int((time.time() - started_at) * 1000)
    return stats
