# 本地 AI 对话知识库 (MVP)

在本地 Mac 上统一收集多 IDE/终端的 AI 对话，并提供：
- 去重入库
- 自动摘要（优先调用本地 Ollama，失败时降级提取式摘要）
- 全文检索（SQLite FTS5）
- Web 查看与搜索

## 1. 启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

浏览器打开：`http://127.0.0.1:8000`

## 2. 写入一条对话

```bash
curl -X POST http://127.0.0.1:8000/api/ingest \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "vscode",
    "session_id": "demo-001",
    "role": "assistant",
    "content": "建议把重试和幂等键一起设计，避免重复写入。"
  }'
```

## 3. 检索

```bash
curl -X POST http://127.0.0.1:8000/api/search \
  -H 'Content-Type: application/json' \
  -d '{"q":"幂等 重试", "limit": 10}'
```

## 4. 接入更多来源（下一步）

建议新增 `connectors/` 目录，每个来源一个适配器：
- `connectors/vscode.py`
- `connectors/terminal.py`
- `connectors/cursor.py`

适配器统一输出 `source/session_id/role/content` 后调用 `/api/ingest` 即可。

## 4.1 一键同步 VSCode/Windsurf 聊天记录

```bash
/Users/bee/Desktop/知识库/.venv/bin/python scripts/sync_ide_chats.py
```

可选参数：

```bash
# 只同步 VSCode
/Users/bee/Desktop/知识库/.venv/bin/python scripts/sync_ide_chats.py --no-windsurf

# 只同步 Windsurf
/Users/bee/Desktop/知识库/.venv/bin/python scripts/sync_ide_chats.py --no-vscode
```

脚本会自动扫描：
- `~/Library/Application Support/Code/User/workspaceStorage/*/chatSessions/*.{json,jsonl}`
- `~/Library/Application Support/Windsurf/User/workspaceStorage/*/chatSessions/*.{json,jsonl}`

并输出同步统计：`files/parsed/inserted/deduped`。

## 5. 可选：本地大模型摘要

安装并运行 Ollama 后，可设置：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5:7b
```

未配置时系统会自动使用提取式摘要，不影响主流程。
