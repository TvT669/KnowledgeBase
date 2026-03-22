from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


def _fallback_summary(text: str, max_len: int = 120) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:max_len] + ("..." if len(clean) > max_len else "")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？!?]\s*|\n+", text)
    return [part.strip(" -:：") for part in parts if part.strip()]


def _clip(text: str, max_len: int = 28) -> str:
    clean = _normalize_whitespace(text)
    return clean[:max_len] + ("..." if len(clean) > max_len else "")


def _pick_sentence(sentences: list[str], keywords: tuple[str, ...]) -> str | None:
    for sentence in sentences:
        if any(keyword in sentence for keyword in keywords):
            return sentence
    return None


def _strip_json_fence(raw: str) -> str:
    fenced = raw.strip()
    if fenced.startswith("```"):
        fenced = re.sub(r"^```(?:json)?", "", fenced)
        fenced = re.sub(r"```$", "", fenced).strip()

    start = fenced.find("{")
    end = fenced.rfind("}")
    if start != -1 and end != -1 and end > start:
        return fenced[start : end + 1]
    return fenced


def _fallback_note_draft(messages: list[dict[str, Any]]) -> dict[str, str]:
    combined = _normalize_whitespace(" ".join(message["content"] for message in messages))
    sentences = _split_sentences(combined)
    first = sentences[0] if sentences else "需要整理的一段技术对话"
    cause = _pick_sentence(
        sentences,
        ("因为", "由于", "根因", "原因", "导致", "缺少", "没有", "未做"),
    )
    solution = _pick_sentence(
        sentences,
        ("建议", "可以", "应该", "修复", "解决", "增加", "加入", "避免", "需要"),
    )

    return {
        "title": _clip(first.replace("建议", "").replace("需要", "").strip("，。 "), 24) or "待整理笔记",
        "problem": first,
        "root_cause": cause or "这段对话没有明确给出单一根因，需要结合上下文继续确认。",
        "solution": solution or _fallback_summary(combined, 120),
        "key_takeaways": _clip(solution or first, 60) or "先沉淀可复用方案，再回看是否能形成通用检查清单。",
    }


async def generate_note_draft(messages: list[dict[str, Any]]) -> dict[str, str]:
    """
    Generate a structured note draft from one or more messages.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    context = "\n\n".join(
        (
            f"[消息 {index}] 来源: {message['source']} / 角色: {message['role']}\n"
            f"{message['content']}"
        )
        for index, message in enumerate(messages, start=1)
    )
    prompt = (
        "请把下面的技术对话整理成一篇结构化中文笔记，并严格输出 JSON。"
        "字段只能包含 title、problem、root_cause、solution、key_takeaways。"
        "每个字段控制在 1-3 句，内容务必具体、可执行，不要输出额外解释。\n\n"
        f"{context}"
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            raw = (resp.json().get("response") or "").strip()
            parsed = json.loads(_strip_json_fence(raw))
            keys = ("title", "problem", "root_cause", "solution", "key_takeaways")
            if all(_normalize_whitespace(str(parsed.get(key, ""))) for key in keys):
                return {key: _normalize_whitespace(str(parsed[key])) for key in keys}
    except Exception:
        pass

    return _fallback_note_draft(messages)


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
