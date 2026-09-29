"""Pytest tests for GraphMind core engine."""
import pytest
from pathlib import Path
import tempfile

from app.core import (
    tokenize, cosine, TfidfEmbedder, VectorIndex,
    chunk_text, split_sections, KnowledgeGraph, GraphMindEngine,
)


# ── tokenize ─────────────────────────────────────────────────────────────────

def test_tokenize_basic():
    tokens = tokenize("Hello World, this is a test.")
    assert "hello" in tokens
    assert "world" in tokens


def test_tokenize_empty():
    assert tokenize("") == []


# ── cosine ────────────────────────────────────────────────────────────────────

def test_cosine_identical():
    v = {"a": 0.6, "b": 0.8}
    assert abs(cosine(v, v) - 1.0) < 1e-6


def test_cosine_orthogonal():
    assert cosine({"a": 1.0}, {"b": 1.0}) == 0.0


def test_cosine_empty():
    assert cosine({}, {"a": 1.0}) == 0.0


# ── TfidfEmbedder ─────────────────────────────────────────────────────────────

def test_tfidf_fit_transform():
    emb = TfidfEmbedder()
    texts = ["neural networks learn features", "knowledge graphs store relations"]
    vectors = emb.fit_transform(texts)
    assert len(vectors) == 2
    for v in vectors:
        assert isinstance(v, dict)
        assert all(isinstance(val, float) for val in v.values())


def test_tfidf_transform_query():
    emb = TfidfEmbedder()
    texts = ["RAG retrieval augmented generation", "knowledge graph triples"]
    emb.fit_transform(texts)
    q = emb.transform("RAG generation")
    assert isinstance(q, dict)
    assert len(q) > 0


def test_tfidf_similarity():
    emb = TfidfEmbedder()
    texts = ["machine learning neural networks", "graph databases and triples", "machine learning optimization"]
    vecs = emb.fit_transform(texts)
    # First and third should be more similar than first and second
    sim_0_2 = cosine(vecs[0], vecs[2])
    sim_0_1 = cosine(vecs[0], vecs[1])
    assert sim_0_2 >= sim_0_1


# ── split_sections ────────────────────────────────────────────────────────────

def test_split_sections_detects_headings():
    text = "INTRODUCTION\nThis is the intro.\nMETHODS\nWe used RAG."
    sections = split_sections(text)
    names = [s[0] for s in sections]
    assert any("INTRODUCTION" in n or "METHODS" in n for n in names)


def test_split_sections_fallback():
    text = "just plain text with no headings here at all"
    sections = split_sections(text)
    assert len(sections) >= 1


# ── chunk_text ────────────────────────────────────────────────────────────────

def test_chunk_text_basic():
    chunks = chunk_text("doc1", "test.txt", "word " * 200, page=1)
    assert len(chunks) >= 1
    for c in chunks:
        assert c.document_id == "doc1"
        assert c.document_name == "test.txt"
        assert c.page == 1
        assert len(c.text) > 0


def test_chunk_text_provenance():
    chunks = chunk_text("docX", "paper.pdf", "The quick brown fox " * 50)
    assert all(c.document_id == "docX" for c in chunks)
    assert all(isinstance(c.index, int) for c in chunks)


def test_chunk_citation():
    chunks = chunk_text("d1", "Nature2024.pdf", "test text", page=5)
    assert "Nature2024.pdf" in chunks[0].citation()
    assert "p. 5" in chunks[0].citation()


# ── VectorIndex ───────────────────────────────────────────────────────────────

def test_vector_index_search():
    idx = VectorIndex()
    chunks = chunk_text("d1", "doc1.txt", "RAG retrieval augmented generation language model") + \
             chunk_text("d2", "doc2.txt", "knowledge graph neo4j triples entities relations")
    idx.build(chunks)
    results = idx.search("retrieval augmented", k=3)
    assert len(results) >= 1
    top_chunk, top_score = results[0]
    assert top_score > 0.0
    assert "d1" in top_chunk.document_id


def test_vector_index_empty():
    idx = VectorIndex()
    assert idx.search("anything", k=5) == []


def test_vector_index_save_load(tmp_path):
    idx = VectorIndex()
    chunks = chunk_text("d1", "doc.txt", "scientific literature question answering")
    idx.build(chunks)
    save_path = tmp_path / "index.json"
    idx.save(save_path)

    idx2 = VectorIndex()
    idx2.load(save_path)
    assert len(idx2.chunks) == len(idx.chunks)


# ── KnowledgeGraph ────────────────────────────────────────────────────────────

def test_kg_extract_triples():
    kg = KnowledgeGraph()
    text = "BERT is a transformer model. RAG uses dense retrieval."
    triples = kg.extract_triples(text)
    assert isinstance(triples, list)


def test_kg_add_and_query():
    kg = KnowledgeGraph()
    text = "Transformer is a neural network architecture. BERT uses Transformer."
    kg.add_document("d1", "paper.txt", text)
    results = kg.neighbours("transformer")
    assert isinstance(results, list)


# ── GraphMindEngine (integration) ─────────────────────────────────────────────

@pytest.fixture
def engine(tmp_path):
    return GraphMindEngine(tmp_path)


def test_engine_demo_seeded(engine):
    assert len(engine.documents) >= 5
    assert len(engine.index.chunks) >= 10


def test_engine_ingest_txt(engine):
    text = b"GraphMind uses hybrid retrieval combining vector search and knowledge graphs for scientific QA."
    doc = engine.ingest("test_paper.txt", text, "text/plain")
    assert "id" in doc
    assert doc["name"] == "test_paper.txt"
    assert len(engine.documents) >= 6


def test_engine_ingest_pdf_fallback(engine):
    # Should not crash even with invalid PDF bytes
    result = engine.ingest("bad.pdf", b"not a real pdf", "application/pdf")
    # Either ingested or returned error — should not raise
    assert isinstance(result, dict)


def test_engine_ask_returns_structure(engine):
    result = engine.ask("What is retrieval augmented generation?", limit=3)
    assert "answer" in result
    assert "evidence" in result
    assert "citations" in result
    assert "confidence" in result
    assert isinstance(result["confidence"], float)
    assert 0.0 <= result["confidence"] <= 1.0


def test_engine_ask_answer_nonempty(engine):
    result = engine.ask("How does RAPTOR improve RAG?", limit=4)
    assert len(result["answer"]) > 10


def test_engine_delete_document(engine):
    doc_id = list(engine.documents.keys())[0]
    assert engine.delete_document(doc_id) is True
    assert doc_id not in engine.documents
    assert engine.delete_document("nonexistent") is False
