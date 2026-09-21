from __future__ import annotations

import json
import math
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable
from .providers import ModelProvider
from .agents import GraphMindOrchestrator

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    id: str
    document_id: str
    document_name: str
    text: str
    page: int | None
    section: str
    index: int
    embedding: dict[str, float] = field(default_factory=dict)

    def citation(self) -> str:
        location = f"p. {self.page}" if self.page else self.section or "document"
        return f"{self.document_name} ({location})"


def tokenize(text: str) -> list[str]:
    return [word.lower() for word in WORD_RE.findall(text)]


class TfidfEmbedder:
    """Small dependency-free embedding fallback suitable for a local prototype."""

    def fit_transform(self, texts: Iterable[str]) -> list[dict[str, float]]:
        tokenized = [tokenize(text) for text in texts]
        document_frequency: Counter[str] = Counter()
        for words in tokenized:
            document_frequency.update(set(words))
        count = max(len(tokenized), 1)
        vectors: list[dict[str, float]] = []
        for words in tokenized:
            counts = Counter(words)
            vector = {
                word: (1 + math.log(frequency)) * math.log((count + 1) / (document_frequency[word] + 1))
                for word, frequency in counts.items()
            }
            norm = math.sqrt(sum(value * value for value in vector.values())) or 1
            vectors.append({word: value / norm for word, value in vector.items()})
        return vectors

    def transform(self, text: str, vocabulary: Iterable[str] | None = None) -> dict[str, float]:
        words = tokenize(text)
        counts = Counter(words)
        allowed = set(vocabulary or counts)
        vector = {word: 1 + math.log(frequency) for word, frequency in counts.items() if word in allowed}
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1
        return {word: value / norm for word, value in vector.items()}


def cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    return sum(value * right.get(key, 0.0) for key, value in left.items())


def split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current = "Introduction"
    buffer: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        is_heading = len(clean) < 90 and (
            clean.isupper() or re.match(r"^(?:\d+(?:\.\d+)*[.)]?\s+)?[A-Z][^.!?]{2,}$", clean)
        )
        if is_heading and buffer:
            sections.append((current, "\n".join(buffer)))
            buffer = []
        if is_heading:
            current = clean
        else:
            buffer.append(clean)
    if buffer:
        sections.append((current, "\n".join(buffer)))
    return sections or [("Document", text.strip())]


def chunk_text(document_id: str, document_name: str, text: str, page: int | None = None, size: int = 900, overlap: int = 140) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section, section_text in split_sections(text):
        words = section_text.split()
        start = 0
        while start < len(words):
            end = min(len(words), start + size // 5)
            content = " ".join(words[start:end]).strip()
            if content:
                chunks.append(Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    document_name=document_name,
                    text=content,
                    page=page,
                    section=section,
                    index=len(chunks),
                ))
            if end >= len(words):
                break
            start = max(end - overlap // 5, start + 1)
    return chunks


class HybridIndex:
    def __init__(self, models: ModelProvider | None = None) -> None:
        self.embedder = TfidfEmbedder()
        self.models = models or ModelProvider()
        self.chunks: list[Chunk] = []

    def add(self, chunks: list[Chunk]) -> None:
        self.chunks.extend(chunks)
        vectors = self.models.embed([chunk.text for chunk in self.chunks]) or self.embedder.fit_transform([chunk.text for chunk in self.chunks])
        for chunk, vector in zip(self.chunks, vectors):
            chunk.embedding = vector

    def search(self, query: str, limit: int = 6, document_id: str | None = None) -> list[dict]:
        query_words = Counter(tokenize(query))
        query_vector = self.models.embed([query])
        query_vector = query_vector[0] if query_vector else self.embedder.transform(query)
        scored = []
        for chunk in self.chunks:
            if document_id and chunk.document_id != document_id:
                continue
            lexical = sum(query_words[word] for word in tokenize(chunk.text) if word in query_words)
            lexical_score = min(lexical / max(sum(query_words.values()), 1), 1.0)
            semantic_score = cosine(query_vector, chunk.embedding)
            score = 0.62 * semantic_score + 0.38 * lexical_score
            scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [{**asdict(chunk), "score": round(score, 4), "citation": chunk.citation()} for score, chunk in scored[:limit]]


@dataclass
class GraphStore:
    nodes: set[str] = field(default_factory=set)
    edges: list[dict[str, str]] = field(default_factory=list)
    available: bool = False

    def ingest(self, chunks: list[Chunk], models: ModelProvider | None = None) -> None:
        for chunk in chunks:
            entities = (models.entities(chunk.text) if models else None) or [word for word in tokenize(chunk.text) if len(word) > 5][:8]
            self.nodes.update(entities)
            for left, right in zip(entities, entities[1:]):
                self.edges.append({"source": left, "target": right, "relation": "co-occurs"})

    def context(self, query: str) -> list[str]:
        terms = set(tokenize(query))
        return [edge["source"] + " relates to " + edge["target"] for edge in self.edges if edge["source"] in terms or edge["target"] in terms][:5]


class GraphMindEngine:
    def __init__(self, data_dir: str | Path = "./data") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.models = ModelProvider()
        self.index = HybridIndex(self.models)
        self.graph = GraphStore()
        self.orchestrator = GraphMindOrchestrator(self.models, self.index.search, self.graph.context)
        self.documents: dict[str, dict] = {}
        self._load()
        if not self.documents:
            self.add_document("demo-literature.txt", DEMO_TEXT, source="demo")

    def _load(self) -> None:
        state = self.data_dir / "index.json"
        if not state.exists():
            return
        payload = json.loads(state.read_text(encoding="utf-8"))
        chunks = [Chunk(**item) for item in payload.get("chunks", [])]
        self.index.add(chunks)
        self.documents = payload.get("documents", {})
        self.graph = GraphStore(**payload.get("graph", {}))

    def _save(self) -> None:
        graph = asdict(self.graph)
        graph["nodes"] = sorted(self.graph.nodes)
        payload = {"documents": self.documents, "chunks": [asdict(chunk) for chunk in self.index.chunks], "graph": graph}
        (self.data_dir / "index.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def add_document(self, name: str, text: str, source: str = "upload") -> dict:
        return self.add_document_pages(name, [(None, text)], source)

    def add_document_pages(self, name: str, pages: list[tuple[int | None, str]], source: str = "upload") -> dict:
        document_id = str(uuid.uuid4())
        chunks = [
            chunk
            for page, text in pages
            for chunk in chunk_text(document_id, name, text, page=page)
        ]
        self.index.add(chunks)
        self.graph.ingest(chunks, self.models)
        metadata = {"id": document_id, "name": name, "source": source, "chunks": len(chunks)}
        self.documents[document_id] = metadata
        self._save()
        return metadata

    def plan(self, question: str) -> dict:
        terms = tokenize(question)
        model_plan = self.models.plan(question)
        return {"question_type": "comparative" if "compare" in terms or "difference" in terms else "factoid", "sub_queries": model_plan["sub_queries"] if model_plan else [question], "entities": model_plan["entities"] if model_plan else terms[:8], "planner": "model" if model_plan else "local"}

    def ask(self, question: str, limit: int = 6, document_id: str | None = None) -> dict:
        workflow = self.orchestrator.run(question, limit, document_id=document_id)
        plan = workflow["plan"]
        evidence = workflow["evidence"]
        graph_context = workflow["graph_context"]
        if evidence:
            answer = self.models.generate(f"Answer the question using only the evidence. Cite the source names inline.\nQuestion: {question}\nEvidence: {' '.join(item['text'] for item in evidence[:4])}") or self._local_answer(question, evidence)
            confidence = min(0.98, 0.42 + sum(item["score"] for item in evidence[:3]) / 3)
            status = "grounded"
        else:
            answer = "I could not find supporting passages in the indexed literature."
            confidence = 0.0
            status = "insufficient_evidence"
        verification = self.models.verify(answer, evidence)
        if verification and verification.get("supported") is False:
            confidence = min(confidence, 0.35)
        return {"question": question, "document_id": document_id, "answer": answer, "confidence": round(confidence, 2), "status": status, "plan": plan, "evidence": evidence, "graph_context": graph_context, "verification": verification or {"supported": bool(evidence), "mode": "local"}, "provider": self.models.status(), "orchestration": {"agents": self.orchestrator.status()["agents"], "messages": workflow["messages"]}}

    def _local_answer(self, question: str, evidence: list[dict]) -> str:
        sentences = []
        terms = set(tokenize(question))
        for item in evidence:
            for sentence in SENTENCE_RE.split(item["text"]):
                if len(terms.intersection(tokenize(sentence))) >= 2:
                    sentences.append(sentence.strip())
                if len(sentences) == 2:
                    break
            if len(sentences) == 2:
                break
        return " ".join(sentences) if sentences else evidence[0]["text"][:420].rstrip() + "..."


DEMO_TEXT = """GraphMind is a practical architecture for question answering over scientific literature.
Retrieval combines lexical matching with local TF-IDF vectors so the demo works without a hosted database or embedding API.

Evidence and provenance
Every passage keeps its source document, section, page when available, and stable chunk identifier. Answers should cite these passages rather than inventing unsupported claims.

Knowledge graphs
Scientific concepts can be represented as entities and co-occurrence relationships. Neo4j is optional; the local graph fallback stores a lightweight relationship index for demonstrations and tests.

Verification
The verifier checks whether an answer has retrieved evidence and lowers confidence when evidence is missing. This makes uncertainty visible instead of returning a confident unsupported response.

Future work
Production deployments can replace the local embedder with a sentence-transformer model and connect an OpenAI-compatible or local Ollama provider without changing the retrieval API."""
