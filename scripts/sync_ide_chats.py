from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

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


async def run_sync(include_vscode: bool, include_windsurf: bool, use_llm_summary: bool = False) -> None:
    import time
    t_start = time.time()
    
    home = Path.home()
    total_files = 0
    total_parsed = 0
    total_inserted = 0

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
    for source, files in targets:
        for chat_file in files:
            file_count += 1
            total_files += 1
            
            t0 = time.time()
            messages = load_messages_from_chat_file(chat_file, source=source)
            t_load = time.time() - t0
            total_parsed += len(messages)
            
            if file_count % 10 == 0:
                print(f"[{time.time():.2f}] Progress: {file_count} files, {total_parsed} msgs", flush=True, file=sys.stderr)

            for msg in messages:
                content = str(msg["content"])
                # Use LLM summary only if explicitly requested (slower); otherwise use first 200 chars
                if use_llm_summary:
                    summary = await summarize_text(content)
                else:
                    summary = content[:200]
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
        f"sync done: files={total_files}, parsed={total_parsed}, inserted={total_inserted}, deduped={total_parsed-total_inserted}, elapsed={elapsed:.2f}s"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync VSCode/Windsurf chats into local DB")
    parser.add_argument("--no-vscode", action="store_true", help="skip vscode source")
    parser.add_argument("--no-windsurf", action="store_true", help="skip windsurf source")
    parser.add_argument("--llm-summary", action="store_true", help="use LLM for summary (slower)")
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
            use_llm_summary=args.llm_summary
        ))
        t1 = time.time()
        print(f"[{t1:.2f}] Sync completed in {t1-t0:.2f}s", flush=True, file=sys.stderr)
    except Exception as e:
        t1 = time.time()
        print(f"[{t1:.2f}] ERROR: {e}", flush=True, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
