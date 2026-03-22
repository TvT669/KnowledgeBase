from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ingest_duplicate_and_search() -> None:
    payload = {
        "source": "pytest",
        "session_id": "pytest-demo-session",
        "role": "assistant",
        "content": "pytest 验证幂等写入和补偿搜索。",
    }

    first = client.post("/api/ingest", json=payload)
    second = client.post("/api/ingest", json=payload)
    search = client.post("/api/search", json={"q": "补偿", "limit": 10})

    assert first.status_code in (200, 409)
    assert second.status_code == 409
    assert search.status_code == 200
    assert any(item["session_id"] == payload["session_id"] for item in search.json()["items"])
