#!/usr/bin/env python3
"""最小化调试脚本，一步步执行同步流程关键步骤。"""
import sys
import time
from pathlib import Path

print(f"[{time.time():.2f}] DEBUG: Script started", flush=True)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print(f"[{time.time():.2f}] DEBUG: Path setup done", flush=True)

# 第1步: 测试导入
try:
    print(f"[{time.time():.2f}] DEBUG: Importing ide_collectors...", flush=True)
    from app.connectors.ide_collectors import discover_vscode_chat_files
    print(f"[{time.time():.2f}] DEBUG: ide_collectors imported OK", flush=True)
except Exception as e:
    print(f"[{time.time():.2f}] ERROR: Failed to import ide_collectors: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 第2步: 测试文件发现
try:
    print(f"[{time.time():.2f}] DEBUG: Discovering VSCode files...", flush=True)
    home = Path.home()
    files = discover_vscode_chat_files(home)
    print(f"[{time.time():.2f}] DEBUG: Found {len(files)} files", flush=True)
    if files:
        print(f"[{time.time():.2f}] DEBUG: First file: {files[0].name}", flush=True)
except Exception as e:
    print(f"[{time.time():.2f}] ERROR: Failed to discover files: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 第3步: 导入其他模块
try:
    print(f"[{time.time():.2f}] DEBUG: Importing load_messages_from_chat_file...", flush=True)
    from app.connectors.ide_collectors import load_messages_from_chat_file
    print(f"[{time.time():.2f}] DEBUG: load_messages_from_chat_file imported OK", flush=True)
except Exception as e:
    print(f"[{time.time():.2f}] ERROR: Failed to import load_messages_from_chat_file: {e}", flush=True)
    sys.exit(1)

# 第4步: 测试读取第一个文件
if files:
    try:
        print(f"[{time.time():.2f}] DEBUG: Loading messages from {files[0].name}...", flush=True)
        msgs = load_messages_from_chat_file(files[0], source="vscode")
        print(f"[{time.time():.2f}] DEBUG: Loaded {len(msgs)} messages", flush=True)
    except Exception as e:
        print(f"[{time.time():.2f}] ERROR: Failed to load messages: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

# 第5步: 导入和测试 insert_message
try:
    print(f"[{time.time():.2f}] DEBUG: Importing insert_message...", flush=True)
    from app.services.ingest import insert_message
    print(f"[{time.time():.2f}] DEBUG: insert_message imported OK", flush=True)
except Exception as e:
    print(f"[{time.time():.2f}] ERROR: Failed to import insert_message: {e}", flush=True)
    sys.exit(1)

# 第6步: 测试异步导入
try:
    print(f"[{time.time():.2f}] DEBUG: Importing asyncio...", flush=True)
    import asyncio
    print(f"[{time.time():.2f}] DEBUG: asyncio imported OK", flush=True)
except Exception as e:
    print(f"[{time.time():.2f}] ERROR: Failed to import asyncio: {e}", flush=True)
    sys.exit(1)

# 第7步: 导入 summarizer （可能卡在这里）
try:
    print(f"[{time.time():.2f}] DEBUG: Importing summarize_text...", flush=True)
    from app.services.summarizer import summarize_text
    print(f"[{time.time():.2f}] DEBUG: summarize_text imported OK", flush=True)
except Exception as e:
    print(f"[{time.time():.2f}] ERROR: Failed to import summarize_text: {e}", flush=True)
    sys.exit(1)

print(f"[{time.time():.2f}] DEBUG: All imports successful", flush=True)
print("SUCCESS: All debug checks passed")
