from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .core import GraphMindEngine
from .auth import AuthStore

DATA_DIR = Path(os.getenv("GRAPHMIND_DATA_DIR", "./data"))
cors_origins = [o.strip() for o in os.getenv("GRAPHMIND_CORS_ORIGINS", "*").split(",") if o.strip()]
require_auth = os.getenv("GRAPHMIND_REQUIRE_AUTH", "false").lower() == "true"

engine = GraphMindEngine(DATA_DIR)
auth = AuthStore(DATA_DIR / "graphmind.sqlite3")

app = FastAPI(
    title="GraphMind API",
    version="0.2.0",
    description="Evidence-first scientific literature QA — hybrid RAG + knowledge graph + multi-agent",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    limit: int = Field(default=6, ge=1, le=20)
    document_id: str | None = Field(default=None, max_length=80)


class Credentials(BaseModel):
    email: str = Field(pattern=r"^[^\@\s]+@[^\@\s]+\.[^\@\s]+$", max_length=254)
    password: str = Field(min_length=10, max_length=128)


# ── Auth dependency ───────────────────────────────────────────────────────────

def current_user(authorization: str | None = Header(default=None)) -> dict | None:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    user = auth.user_for_token(token)
    if require_auth and not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


# ── Health / Config ───────────────────────────────────────────────────────────

@app.get("/")
def root() -> dict:
    return {"service": "graphmind-api", "version": "0.2.0", "health": "/api/health"}


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "documents": len(engine.documents),
        "chunks": len(engine.index.chunks),
        "neo4j": engine.graph.available,
        "provider": engine.models.status(),
        "agents": engine.orchestrator.status()["agents"],
    }


@app.get("/api/config")
def config() -> dict:
    return {
        "provider": engine.models.status(),
        "require_auth": require_auth,
        "data_dir": str(DATA_DIR),
    }


# ── Documents ─────────────────────────────────────────────────────────────────

@app.get("/api/documents")
def list_documents(_user: dict | None = Depends(current_user)) -> list:
    return list(engine.documents.values())


@app.post("/api/documents")
async def upload_document(
    file: UploadFile = File(...),
    _user: dict | None = Depends(current_user),
) -> dict:
    if file.size and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    content = await file.read()
    result = engine.ingest(file.filename or "upload", content, file.content_type or "")
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return result


@app.delete("/api/documents/{document_id}")
def delete_document(
    document_id: str,
    _user: dict | None = Depends(current_user),
) -> dict:
    if not engine.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": document_id}


# ── Query / Ask ───────────────────────────────────────────────────────────────

@app.post("/api/ask")
def ask(
    body: AskRequest,
    _user: dict | None = Depends(current_user),
) -> dict:
    if not engine.index.chunks:
        raise HTTPException(status_code=503, detail="No documents indexed yet")
    return engine.ask(body.question, limit=body.limit, document_id=body.document_id)


# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.post("/api/auth/register", status_code=201)
def register(creds: Credentials) -> dict:
    user = auth.register(creds.email, creds.password)
    if not user:
        raise HTTPException(status_code=409, detail="Email already registered")
    return user


@app.post("/api/auth/login")
def login(creds: Credentials) -> dict:
    token = auth.login(creds.email, creds.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token}


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    if token:
        auth.logout(token)
    return {"status": "logged out"}


@app.get("/api/auth/me")
def me(user: dict | None = Depends(current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
