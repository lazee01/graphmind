"""Pytest integration tests for GraphMind FastAPI routes."""
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path


@pytest.fixture
def app(monkeypatch, data_dir):
    import os
    monkeypatch.setenv("GRAPHMIND_DATA_DIR", str(data_dir))
    monkeypatch.setenv("GRAPHMIND_REQUIRE_AUTH", "false")
    # Import fresh app with patched env
    import importlib
    import app.main as m
    importlib.reload(m)
    return m.app


@pytest.mark.anyio
async def test_root(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert resp.json()["service"] == "graphmind-api"


@pytest.mark.anyio
async def test_health(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "documents" in data
    assert "chunks" in data


@pytest.mark.anyio
async def test_list_documents(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 5  # demo corpus seeded


@pytest.mark.anyio
async def test_upload_txt(app):
    content = b"GraphMind is a hybrid RAG system for scientific question answering using knowledge graphs."
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/documents",
            files={"file": ("test.txt", content, "text/plain")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["name"] == "test.txt"


@pytest.mark.anyio
async def test_ask_question(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ask",
            json={"question": "What is retrieval augmented generation?", "limit": 3},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "evidence" in data
    assert "citations" in data
    assert len(data["answer"]) > 5


@pytest.mark.anyio
async def test_ask_with_document_filter(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        docs = (await client.get("/api/documents")).json()
        doc_id = docs[0]["id"]
        resp = await client.post(
            "/api/ask",
            json={"question": "explain this document", "limit": 3, "document_id": doc_id},
        )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_auth_register_login_logout(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register
        reg = await client.post(
            "/api/auth/register",
            json={"email": "test@graphmind.ai", "password": "SecurePass123!"},
        )
        assert reg.status_code == 201
        assert reg.json()["email"] == "test@graphmind.ai"

        # Login
        login = await client.post(
            "/api/auth/login",
            json={"email": "test@graphmind.ai", "password": "SecurePass123!"},
        )
        assert login.status_code == 200
        token = login.json()["token"]
        assert len(token) > 10

        # /me
        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "test@graphmind.ai"

        # Logout
        lo = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert lo.status_code == 200

        # /me after logout should fail
        me2 = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me2.status_code == 401


@pytest.mark.anyio
async def test_register_duplicate(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        creds = {"email": "dup@graphmind.ai", "password": "SecurePass123!"}
        await client.post("/api/auth/register", json=creds)
        resp = await client.post("/api/auth/register", json=creds)
    assert resp.status_code == 409


@pytest.mark.anyio
async def test_config_endpoint(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/config")
    assert resp.status_code == 200
    assert "provider" in resp.json()
