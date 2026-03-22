from __future__ import annotations

import os
import re
from typing import Optional

import httpx


def _fallback_summary(text: str, max_len: int = 120) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:max_len] + ("..." if len(clean) > max_len else "")


async def summarize_text(text: str) -> str:
    """
    Try local Ollama first; if unavailable, fallback to extractive summary.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    prompt = (
        "请将下面技术对话提炼成 2-3 句中文要点，突出结论、风险和可执行动作：\n\n"
        f"{text}"
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
            answer = (data.get("response") or "").strip()
            return answer or _fallback_summary(text)
    except Exception:
        return _fallback_summary(text)
