"""NOVA — Backend Tests: API Endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "NOVA"


@pytest.mark.asyncio
async def test_conversations_list(client):
    resp = await client.get("/api/conversations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_notes_crud(client):
    # Create
    resp = await client.post("/api/notes", json={"title": "Test Note", "content": "test content"})
    assert resp.status_code == 200
    note = resp.json()
    assert note["title"] == "Test Note"
    note_id = note["id"]

    # List
    resp = await client.get("/api/notes")
    assert resp.status_code == 200
    notes = resp.json()
    assert any(n["id"] == note_id for n in notes)

    # Update
    resp = await client.put(f"/api/notes/{note_id}", json={"title": "Updated Note"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Note"

    # Delete
    resp = await client.delete(f"/api/notes/{note_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_reminders_crud(client):
    # Create
    resp = await client.post("/api/reminders", json={"title": "Test Reminder"})
    assert resp.status_code == 200
    rem = resp.json()
    assert rem["title"] == "Test Reminder"
    rem_id = rem["id"]

    # List
    resp = await client.get("/api/reminders")
    assert resp.status_code == 200

    # Delete
    resp = await client.delete(f"/api/reminders/{rem_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_documents_list(client):
    resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_memory_crud(client):
    # Create
    resp = await client.post("/api/memory", json={"content": "Test memory", "category": "test"})
    assert resp.status_code == 200
    mem_id = resp.json()["id"]

    # List
    resp = await client.get("/api/memory")
    assert resp.status_code == 200

    # Delete
    resp = await client.delete(f"/api/memory/{mem_id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_analytics(client):
    resp = await client.get("/api/analytics")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_conversations" in data
    assert "total_messages" in data
    assert "avg_response_latency_ms" in data


@pytest.mark.asyncio
async def test_chat_stream_endpoint(client):
    resp = await client.post("/api/chat/stream", json={"message": "what time is it"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    content = resp.text
    assert "data:" in content
    assert "state" in content or "token" in content
    assert '"type": "done"' in content or '"type":"done"' in content
    assert "get_current_time" in content


@pytest.mark.asyncio
async def test_wake_check_endpoint(client):
    # Short dummy audio clip
    dummy_wav = b"RIFF" + b"\x00" * 2000
    files = {"file": ("wake.wav", dummy_wav, "audio/wav")}
    resp = await client.post("/api/voice/wake-check", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert "detected" in data
    assert isinstance(data["detected"], bool)

