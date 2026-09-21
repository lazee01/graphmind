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
cors_origins = [origin.strip() for origin in os.getenv("GRAPHMIND_CORS_ORIGINS", "*").split(",") if origin.strip()]
engine = GraphMindEngine(DATA_DIR)
auth = AuthStore(DATA_DIR / "graphmind.sqlite3")
require_auth = os.getenv("GRAPHMIND_REQUIRE_AUTH", "false").lower() == "true"
app = FastAPI(title="GraphMind API", version="0.1.0", description="Provenance-aware scientific literature QA prototype")
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["*"], allow_headers=["*"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    limit: int = Field(default=6, ge=1, le=20)


class Credentials(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    password: str = Field(min_length=10, max_length=128)


def current_user(authorization: str | None = Header(default=None)) -> dict | None:
    token = authorization.removeprefix("Bearer ").strip() if authorization else None
    user = auth.user_for_token(token)
    if require_auth and not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "documents": len(engine.documents), "chunks": len(engine.index.chunks), "neo4j": engine.graph.available, "provider": engine.models.status(), "agents": engine.orchestrator.status()["agents"]}


@app.get("/")
def root() -> dict:
    return {"service": "graphmind-api", "health": "/api/health"}


@app.get("/api/config")
def config() -> dict:
    return {"models": engine.models.status(), "orchestration": engine.orchestrator.status(), "auth": {"required": require_auth, "sessions": "sqlite"}, "vector_store": "sentence-transformers-or-local-tfidf", "graph_store": "neo4j" if engine.graph.available else "local-fallback", "features": {"pdf_upload": True, "provenance": True, "hybrid_retrieval": True, "answer_generation": True, "planner": True, "verification": True, "entity_extraction": True, "ocr": True}}


@app.post("/api/auth/register")
def register(credentials: Credentials) -> dict:
    try:
        return auth.register(credentials.email, credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.post("/api/auth/login")
def login(credentials: Credentials) -> dict:
    try:
        user, token = auth.login(credentials.email, credentials.password)
        return {"user": user, "access_token": token, "token_type": "bearer"}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict:
    auth.logout(authorization.removeprefix("Bearer ").strip() if authorization else None)
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: dict | None = Depends(current_user)) -> dict:
    return {"user": user}


@app.get("/api/documents")
def documents(_: dict | None = Depends(current_user)) -> list[dict]:
    return list(engine.documents.values())


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), _: dict | None = Depends(current_user)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum upload size is 25 MB")
    if file.filename.lower().endswith(".pdf"):
        try:
            try:
                import fitz
                page_text = [(index + 1, page.get_text()) for index, page in enumerate(fitz.open(stream=raw, filetype="pdf"))]
            except ImportError:
                from pypdf import PdfReader
                pages = PdfReader(BytesIO(raw)).pages
                page_text = [(index + 1, page.extract_text() or "") for index, page in enumerate(pages)]
            if not any(text.strip() for _, text in page_text):
                raise ValueError("OCR required")
        except Exception as exc:
            try:
                from pdf2image import convert_from_bytes
                import pytesseract
                page_text = [(index + 1, pytesseract.image_to_string(image)) for index, image in enumerate(convert_from_bytes(raw, dpi=180))]
            except ImportError:
                raise HTTPException(status_code=422, detail=f"PDF has no extractable text; install optional OCR dependencies (pdf2image, pytesseract, Tesseract). Details: {exc}") from exc
    else:
        page_text = [(None, raw.decode("utf-8", errors="replace"))]
    if not any(text.strip() for _, text in page_text):
        raise HTTPException(status_code=422, detail="The document contains no extractable text")
    return engine.add_document_pages(file.filename, page_text)


@app.post("/api/ask")
def ask(request: AskRequest, _: dict | None = Depends(current_user)) -> dict:
    return engine.ask(request.question, request.limit)
