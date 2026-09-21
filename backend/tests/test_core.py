from app.core import GraphMindEngine, chunk_text


def test_chunks_keep_provenance():
    chunks = chunk_text("doc-1", "paper.txt", "INTRODUCTION\nRetrieval systems use evidence.\nMETHODS\nA local index stores provenance.")
    assert chunks
    assert all(chunk.document_id == "doc-1" for chunk in chunks)
    assert {chunk.section for chunk in chunks} == {"INTRODUCTION", "METHODS"}


def test_engine_returns_grounded_citations(tmp_path):
    engine = GraphMindEngine(tmp_path)
    engine.add_document("paper.txt", "Retrieval uses evidence and provenance to support scientific answers.")
    result = engine.ask("How does retrieval support answers?")
    assert result["status"] == "grounded"
    assert result["evidence"]
    assert result["evidence"][0]["citation"].startswith("paper.txt")


def test_engine_is_explicit_when_empty(tmp_path):
    engine = GraphMindEngine(tmp_path)
    engine.index.chunks.clear()
    result = engine.ask("What is quantum teleportation?")
    assert result["status"] == "insufficient_evidence"
