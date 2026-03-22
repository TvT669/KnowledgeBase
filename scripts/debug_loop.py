#!/usr/bin/env python3
"""完整循环测试，执行所有 118 个文件的解析和第一条消息的插入。"""
import sys
import time
from pathlib import Path

print(f"[{time.time():.2f}] START", flush=True)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.connectors.ide_collectors import discover_vscode_chat_files, load_messages_from_chat_file
from app.services.ingest import insert_message

home = Path.home()
files = discover_vscode_chat_files(home)
print(f"[{time.time():.2f}] Found {len(files)} files", flush=True)

total_parsed = 0
total_inserted = 0

for i, chat_file in enumerate(files[:5]):  # 先测试前 5 个文件
    try:
        t0 = time.time()
        messages = load_messages_from_chat_file(chat_file, source="vscode")
        t1 = time.time()
        print(f"[{t1:.2f}] File {i+1}/5: {chat_file.name[:20]}... | parsed {len(messages)} msgs in {t1-t0:.3f}s", flush=True)
        
        total_parsed += len(messages)
        
        # 只插入第一条消息作为测试
        if messages:
            msg = messages[0]
            content = str(msg["content"])
            summary = content[:200]
            
            t2 = time.time()
            inserted, row_id = insert_message(
                source=str(msg["source"]),
                session_id=str(msg.get("session_id") or ""),
                role=str(msg["role"]),
                content=content,
                summary=summary,
            )
            t3 = time.time()
            
            if inserted:
                total_inserted += 1
                print(f"  -> Inserted row {row_id} in {t3-t2:.3f}s", flush=True)
            else:
                print(f"  -> Deduplicated (already existed)", flush=True)
    except Exception as e:
        print(f"[{time.time():.2f}] ERROR in file {i+1}: {e}", flush=True)
        import traceback
        traceback.print_exc()

print(f"[{time.time():.2f}] DONE: parsed={total_parsed}, inserted={total_inserted}", flush=True)
