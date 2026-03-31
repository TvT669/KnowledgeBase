from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import sys
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.ide_collectors import (
    discover_vscode_chat_files,
    discover_windsurf_chat_files,
    load_messages_from_chat_file,
)
from app.services.ingest import insert_message
from app.services.summarizer import summarize_text


def _default_device_name() -> str:
    hostname = socket.gethostname().strip().replace(" ", "-")
    return hostname or "device"


def _build_remote_state_file(remote_base_url: str, device_name: str) -> Path:
    digest = hashlib.sha1(remote_base_url.encode("utf-8")).hexdigest()[:8]
    return Path.home() / ".knowledgebase" / f"remote-sync-{device_name}-{digest}.json"


def _load_remote_state(path: Path) -> dict[str, dict[str, int]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    cleaned: dict[str, dict[str, int]] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        cleaned[str(key)] = {
            "size": int(value.get("size") or 0),
            "mtime_ns": int(value.get("mtime_ns") or 0),
        }
    return cleaned


def _save_remote_state(path: Path, state: dict[str, dict[str, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _state_key(source: str, file_path: Path) -> str:
    return f"{source}|{file_path}"


def _file_signature(file_path: Path) -> dict[str, int]:
    stat = file_path.stat()
    return {"size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns)}


def _chunked(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _decorate_session_id(session_id: str | None, *, device_name: str, remote_base_url: str | None) -> str | None:
    if not session_id or not remote_base_url:
        return session_id
    return f"{device_name}:{session_id}"


async def _build_summary(content: str, *, use_llm_summary: bool) -> str:
    if not use_llm_summary:
        return content[:200]
    return await summarize_text(content)


async def _upload_remote_batch(
    client: httpx.AsyncClient,
    *,
    remote_base_url: str,
    api_token: str | None,
    items: list[dict[str, Any]],
) -> tuple[int, int]:
    headers = {"Content-Type": "application/json"}
    if api_token:
        headers["X-Knowledge-Token"] = api_token

    response = await client.post(
        f"{remote_base_url.rstrip('/')}/api/ingest/batch",
        headers=headers,
        json={"items": items},
    )
    if response.status_code == 401:
        raise RuntimeError("remote ingest unauthorized: check KNOWLEDGE_API_TOKEN / --api-token")
    if not response.is_success:
        detail = response.text.strip() or f"remote ingest failed: {response.status_code}"
        raise RuntimeError(detail)

    data = response.json()
    return int(data.get("inserted_count") or 0), int(data.get("deduped_count") or 0)


async def run_sync(
    include_vscode: bool,
    include_windsurf: bool,
    use_llm_summary: bool = False,
    *,
    remote_base_url: str | None = None,
    api_token: str | None = None,
    device_name: str | None = None,
    state_file: Path | None = None,
) -> None:
    import time

    t_start = time.time()
    home = Path.home()
    total_files = 0
    total_parsed = 0
    total_inserted = 0
    total_skipped = 0
    resolved_device_name = str(device_name or _default_device_name()).strip() or "device"
    remote_state: dict[str, dict[str, int]] = {}
    resolved_state_file: Path | None = None
    if remote_base_url:
        resolved_state_file = state_file or _build_remote_state_file(remote_base_url, resolved_device_name)
        remote_state = _load_remote_state(resolved_state_file)

    targets: list[tuple[str, list[Path]]] = []
    if include_vscode:
        t0 = time.time()
        vscode_files = discover_vscode_chat_files(home)
        print(f"[{time.time():.2f}] VSCode discovery: {len(vscode_files)} files in {time.time()-t0:.2f}s", flush=True, file=sys.stderr)
        targets.append(("vscode", vscode_files))
    if include_windsurf:
        t0 = time.time()
        windsurf_files = discover_windsurf_chat_files(home)
        print(f"[{time.time():.2f}] Windsurf discovery: {len(windsurf_files)} files in {time.time()-t0:.2f}s", flush=True, file=sys.stderr)
        targets.append(("windsurf", windsurf_files))

    file_count = 0
    async with httpx.AsyncClient(timeout=60.0) if remote_base_url else _null_async_client() as client:
        for source, files in targets:
            for chat_file in files:
                file_count += 1
                total_files += 1

                cache_key = _state_key(source, chat_file)
                signature = _file_signature(chat_file)
                if remote_base_url and remote_state.get(cache_key) == signature:
                    total_skipped += 1
                    if file_count % 10 == 0:
                        print(
                            f"[{time.time():.2f}] Progress: {file_count} files, {total_parsed} msgs, skipped={total_skipped}",
                            flush=True,
                            file=sys.stderr,
                        )
                    continue

                messages = load_messages_from_chat_file(chat_file, source=source)
                total_parsed += len(messages)

                if file_count % 10 == 0:
                    print(
                        f"[{time.time():.2f}] Progress: {file_count} files, {total_parsed} msgs, skipped={total_skipped}",
                        flush=True,
                        file=sys.stderr,
                    )

                if remote_base_url:
                    payload_items: list[dict[str, str | None]] = []
                    for msg in messages:
                        content = str(msg["content"])
                        payload_items.append(
                            {
                                "source": str(msg["source"]),
                                "session_id": _decorate_session_id(
                                    str(msg.get("session_id") or ""),
                                    device_name=resolved_device_name,
                                    remote_base_url=remote_base_url,
                                ),
                                "role": str(msg["role"]),
                                "content": content,
                                "summary": await _build_summary(content, use_llm_summary=use_llm_summary),
                            }
                        )
                    inserted_count = 0
                    for chunk in _chunked(payload_items, 200):
                        chunk_inserted, _ = await _upload_remote_batch(
                            client,
                            remote_base_url=remote_base_url,
                            api_token=api_token,
                            items=chunk,
                        )
                        inserted_count += chunk_inserted
                    total_inserted += inserted_count
                    remote_state[cache_key] = signature
                    if resolved_state_file is not None:
                        _save_remote_state(resolved_state_file, remote_state)
                    continue

                for msg in messages:
                    content = str(msg["content"])
                    summary = await _build_summary(content, use_llm_summary=use_llm_summary)
                    inserted, _ = insert_message(
                        source=str(msg["source"]),
                        session_id=str(msg.get("session_id") or ""),
                        role=str(msg["role"]),
                        content=content,
                        summary=summary,
                    )
                    if inserted:
                        total_inserted += 1

    elapsed = time.time() - t_start
    print(
        f"sync done: files={total_files}, parsed={total_parsed}, inserted={total_inserted}, deduped={total_parsed-total_inserted}, skipped={total_skipped}, elapsed={elapsed:.2f}s"
    )


class _null_async_client:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync VSCode/Windsurf chats into local DB")
    parser.add_argument("--no-vscode", action="store_true", help="skip vscode source")
    parser.add_argument("--no-windsurf", action="store_true", help="skip windsurf source")
    parser.add_argument("--llm-summary", action="store_true", help="use LLM for summary (slower)")
    parser.add_argument("--remote-base-url", default="", help="upload to a remote knowledge hub instead of the local DB")
    parser.add_argument("--api-token", default="", help="token for remote /api/ingest endpoints")
    parser.add_argument("--device-name", default="", help="logical device name used to namespace remote session ids")
    parser.add_argument("--state-file", default="", help="override the remote sync cache file path")
    return parser.parse_args()


if __name__ == "__main__":
    import time
    t0 = time.time()
    print(f"[{t0:.2f}] Sync started", flush=True, file=sys.stderr)
    
    args = parse_args()
    try:
        asyncio.run(run_sync(
            include_vscode=not args.no_vscode,
            include_windsurf=not args.no_windsurf,
            use_llm_summary=args.llm_summary,
            remote_base_url=str(args.remote_base_url or "").strip() or None,
            api_token=str(args.api_token or "").strip() or None,
            device_name=str(args.device_name or "").strip() or None,
            state_file=Path(args.state_file).expanduser() if str(args.state_file or "").strip() else None,
        ))
        t1 = time.time()
        print(f"[{t1:.2f}] Sync completed in {t1-t0:.2f}s", flush=True, file=sys.stderr)
    except Exception as e:
        t1 = time.time()
        print(f"[{t1:.2f}] ERROR: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
