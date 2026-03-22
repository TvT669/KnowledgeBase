from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def discover_vscode_chat_files(home: Path) -> list[Path]:
    base = home / "Library/Application Support/Code/User/workspaceStorage"
    return _discover_chat_files(base)


def discover_windsurf_chat_files(home: Path) -> list[Path]:
    base = home / "Library/Application Support/Windsurf/User/workspaceStorage"
    return _discover_chat_files(base)


def _discover_chat_files(base: Path) -> list[Path]:
    if not base.exists():
        return []

    paths: list[Path] = []
    for ext in ("*.json", "*.jsonl"):
        paths.extend(base.glob(f"*/chatSessions/{ext}"))
    return sorted(set(paths))


def load_messages_from_chat_file(file_path: Path, source: str) -> list[dict[str, str | None]]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    session_id = file_path.stem

    if file_path.suffix == ".jsonl":
        records = [_safe_json_loads(line) for line in text.splitlines() if line.strip()]
    else:
        records = [_safe_json_loads(text)]

    messages: list[dict[str, str | None]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        messages.extend(_extract_messages_from_record(record, source=source, session_id=session_id))

    return messages


def _extract_messages_from_record(
    record: dict[str, Any], source: str, session_id: str
) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []

    root = record.get("v") if isinstance(record.get("v"), dict) else record
    requests = root.get("requests") if isinstance(root, dict) else None

    if isinstance(requests, list):
        for req in requests:
            if not isinstance(req, dict):
                continue

            user_text = _extract_user_text(req)
            if user_text:
                out.append(
                    {
                        "source": source,
                        "session_id": session_id,
                        "role": "user",
                        "content": user_text,
                    }
                )

            assistant_text = _extract_assistant_text(req)
            if assistant_text:
                out.append(
                    {
                        "source": source,
                        "session_id": session_id,
                        "role": "assistant",
                        "content": assistant_text,
                    }
                )

    return out


def _extract_user_text(req: dict[str, Any]) -> str | None:
    msg = req.get("message")
    if isinstance(msg, dict):
        text = msg.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _extract_assistant_text(req: dict[str, Any]) -> str | None:
    response = req.get("response")
    if not isinstance(response, list):
        return None

    candidates: list[str] = []
    for item in response:
        if not isinstance(item, dict):
            continue

        value = item.get("value")
        if isinstance(value, str):
            v = value.strip()
            if _looks_like_content(v):
                candidates.append(v)

    return candidates[-1] if candidates else None


def _looks_like_content(text: str) -> bool:
    if not text:
        return False
    if text in {"```", "````"}:
        return False
    if text.startswith("正在") and len(text) < 40:
        return False
    if text.startswith("已运行") and len(text) < 50:
        return False
    return True


def _safe_json_loads(raw: str) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return None
