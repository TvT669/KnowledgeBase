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

并输出同步统计：`files/parsed/inserted/deduped/skipped`。

## 4.2 多台电脑共用同一份笔记库

最省事的做法是：
- 选一台常在线机器当中心库
- 中心库运行这个 Web 服务
- 家里电脑、公司电脑只负责扫描本机 IDE 聊天并上传到中心库
- 所有设备通过 Tailscale 访问同一个中心地址

### 中心机启动

```bash
./scripts/setup_center_machine.sh
./scripts/install_center_launch_agent.sh
```

默认会：
- 把运行时副本放到 `~/Library/Application Support/KnowledgeBase/runtime`
- 把数据库放到 `~/Library/Application Support/KnowledgeBase/data/knowledge.db`
- 生成 API token 到 `~/Library/Application Support/KnowledgeBase/api_token`
- 在 `8787` 端口启动中心机，避免和本地开发常用的 `8000` 冲突

快速自检：

```bash
curl http://127.0.0.1:8787/health
```

推荐把中心机加入同一个 Tailscale 网络，然后在其他设备上访问：

```text
http://<tailscale-ip>:8787
```

macOS 上建议直接安装并登录官方 `Tailscale.app`。
仅用 `brew services start tailscale` 启动用户态 `tailscaled` 往往不够，因为它需要 root 权限或官方 app 的系统组件。

### 其他电脑上传到中心库

在家里电脑 / 公司电脑上运行：

```bash
python scripts/sync_ide_chats.py \
  --remote-base-url http://<tailscale-ip>:8787 \
  --api-token "$KNOWLEDGE_API_TOKEN" \
  --device-name office-mac
```

可选参数：

```bash
# 只上传 VSCode 聊天
python scripts/sync_ide_chats.py \
  --remote-base-url http://<tailscale-ip>:8787 \
  --api-token "$KNOWLEDGE_API_TOKEN" \
  --device-name office-mac \
  --no-windsurf

# 自定义远端同步缓存文件
python scripts/sync_ide_chats.py \
  --remote-base-url http://<tailscale-ip>:8787 \
  --api-token "$KNOWLEDGE_API_TOKEN" \
  --device-name office-mac \
  --state-file ~/.knowledgebase/office-sync-state.json
```

说明：
- 远端模式会调用中心机的 `/api/ingest/batch`
- 同步脚本会在本机记录文件签名缓存，后续只上传有变化的聊天文件
- 远端模式下会自动把 `session_id` 加上 `device-name:` 前缀，避免不同设备之间的会话 ID 冲突
- 如果中心机没有设置 `KNOWLEDGE_API_TOKEN`，也可以不传 `--api-token`，但不建议

### 推荐部署方式

- 中心机：家里 Mac mini / 一台常开电脑 / 小型 VPS
- 网络：Tailscale
- 浏览器：所有设备都直接打开中心机的 Web 页面
- 数据库：只保留中心机这一份 `knowledge.db`

## 5. 可选：本地大模型摘要

安装并运行 Ollama 后，可设置：

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=qwen2.5:7b
```

未配置时系统会自动使用提取式摘要，不影响主流程。
