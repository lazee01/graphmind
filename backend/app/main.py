from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .core import GraphMindEngine

DATA_DIR = Path(os.getenv("GRAPHMIND_DATA_DIR", "./data"))
engine = GraphMindEngine(DATA_DIR)
app = FastAPI(title="GraphMind API", version="0.1.0", description="Provenance-aware scientific literature QA prototype")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    limit: int = Field(default=6, ge=1, le=20)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "documents": len(engine.documents), "chunks": len(engine.index.chunks), "neo4j": engine.graph.available, "provider": os.getenv("GRAPHMIND_LLM_PROVIDER", "local")}


@app.get("/api/config")
def config() -> dict:
    return {"llm_provider": os.getenv("GRAPHMIND_LLM_PROVIDER", "local"), "vector_store": "local-tfidf", "graph_store": "neo4j" if engine.graph.available else "local-fallback", "features": {"pdf_upload": True, "provenance": True, "hybrid_retrieval": True, "answer_generation": True}}


@app.get("/api/documents")
def documents() -> list[dict]:
    return list(engine.documents.values())


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    raw = await file.read()
    if file.filename.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
            pages = PdfReader(BytesIO(raw)).pages
            page_text = [(index + 1, page.extract_text() or "") for index, page in enumerate(pages)]
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"PDF extraction failed: {exc}") from exc
    else:
        page_text = [(None, raw.decode("utf-8", errors="replace"))]
    if not any(text.strip() for _, text in page_text):
        raise HTTPException(status_code=422, detail="The document contains no extractable text")
    return engine.add_document_pages(file.filename, page_text)


@app.post("/api/ask")
def ask(request: AskRequest) -> dict:
    return engine.ask(request.question, request.limit)
