"""GraphMind core engine — ingestion, indexing, retrieval, and orchestration.

Local-first design: zero ML dependencies required. Activate optional providers
via the GRAPHMIND_MODEL_PROVIDER environment variable.
"""

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

# ── Data Models ───────────────────────────────────────────────────────────────

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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(**d)


# ── TF-IDF Embedder ───────────────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


class TfidfEmbedder:
    """Dependency-free TF-IDF sparse embedding for local prototype mode."""

    def fit_transform(self, texts: Iterable[str]) -> list[dict[str, float]]:
        tokenized = [tokenize(t) for t in texts]
        df: Counter[str] = Counter()
        for words in tokenized:
            df.update(set(words))
        N = max(len(tokenized), 1)
        vectors: list[dict[str, float]] = []
        for words in tokenized:
            tf = Counter(words)
            vec = {
                w: (1 + math.log(c)) * math.log((N + 1) / (df[w] + 1))
                for w, c in tf.items()
            }
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            vectors.append({w: v / norm for w, v in vec.items()})
        return vectors

    def transform(self, text: str, vocabulary: Iterable[str] | None = None) -> dict[str, float]:
        words = tokenize(text)
        tf = Counter(words)
        allowed = set(vocabulary) if vocabulary else set(tf)
        vec = {w: 1 + math.log(c) for w, c in tf.items() if w in allowed}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {w: v / norm for w, v in vec.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    return sum(a[k] * b.get(k, 0.0) for k in a)


# ── Section & Chunking ────────────────────────────────────────────────────────

def split_sections(text: str) -> list[tuple[str, str]]:
    """Detect section boundaries using heuristics."""
    sections: list[tuple[str, str]] = []
    current = "Introduction"
    buf: list[str] = []
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        is_heading = len(clean) < 90 and (
            clean.isupper()
            or re.match(r"^(?:\d+(?:\.\d+)*[.)]?\s+)?[A-Z][^.!?]{2,80}$", clean)
        )
        if is_heading and buf:
            sections.append((current, "\n".join(buf)))
            buf = []
        if is_heading:
            current = clean
        else:
            buf.append(clean)
    if buf:
        sections.append((current, "\n".join(buf)))
    return sections or [("Document", text.strip())]


def chunk_text(
    document_id: str,
    document_name: str,
    text: str,
    page: int | None = None,
    size: int = 900,
    overlap: int = 140,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    for section, section_text in split_sections(text):
        words = section_text.split()
        word_size = max(size // 5, 30)
        word_overlap = max(overlap // 5, 5)
        start = 0
        while start < len(words):
            end = min(len(words), start + word_size)
            content = " ".join(words[start:end]).strip()
            if content:
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        document_id=document_id,
                        document_name=document_name,
                        text=content,
                        page=page,
                        section=section,
                        index=idx,
                    )
                )
                idx += 1
            start += word_size - word_overlap
    return chunks


# ── Vector Index ──────────────────────────────────────────────────────────────

class VectorIndex:
    """In-memory TF-IDF vector index with optional dense embedding overlay."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._embedder = TfidfEmbedder()
        self._vocab: set[str] = set()

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        vectors = self._embedder.fit_transform(c.text for c in chunks)
        for chunk, vec in zip(chunks, vectors):
            chunk.embedding = vec
            self._vocab.update(vec)

    def add(self, new_chunks: list[Chunk]) -> None:
        """Incrementally add chunks and rebuild index."""
        self.chunks.extend(new_chunks)
        self.build(self.chunks)

    def search(self, query: str, k: int = 6) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        q_vec = self._embedder.transform(query, self._vocab)
        scored = [(c, cosine(q_vec, c.embedding)) for c in self.chunks]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(c, s) for c, s in scored[:k] if s > 0.0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [c.to_dict() for c in self.chunks]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def load(self, path: Path) -> None:
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.chunks = [Chunk.from_dict(d) for d in data]
        # Rebuild vocab from loaded embeddings
        for c in self.chunks:
            self._vocab.update(c.embedding)


# ── Knowledge Graph ───────────────────────────────────────────────────────────

class KnowledgeGraph:
    """Lightweight in-process knowledge graph with optional Neo4j backend."""

    def __init__(self) -> None:
        self._local: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._neo4j: Any = None
        self.available = self._try_neo4j()

    def _try_neo4j(self) -> bool:
        uri = os.getenv("NEO4J_URI", "")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "graphmind")
        if not uri:
            return False
        try:
            from neo4j import GraphDatabase  # type: ignore
            self._neo4j = GraphDatabase.driver(uri, auth=(user, pwd))
            self._neo4j.verify_connectivity()
            return True
        except Exception:
            return False

    def extract_triples(self, text: str) -> list[tuple[str, str, str]]:
        """Extract (subject, relation, object) triples via regex patterns."""
        triples: list[tuple[str, str, str]] = []
        # Pattern: "X is/are/uses/enables Y"
        patterns = [
            r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(is|are|uses|enables|improves|reduces|increases|outperforms)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
            r"([A-Z]{2,})\s+(is|enables|uses|improves)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                subj, rel, obj = m.group(1).strip(), m.group(2).upper(), m.group(3).strip()
                if len(subj) > 2 and len(obj) > 2:
                    triples.append((subj, rel, obj))
        return triples[:30]

    def add_document(self, doc_id: str, doc_name: str, text: str) -> None:
        """Extract and store triples from a document."""
        triples = self.extract_triples(text)
        for subj, rel, obj in triples:
            self._local[subj.lower()].append((rel, obj))
            self._local[obj.lower()].append((f"IS_{rel}_BY", subj))

        if self._neo4j:
            try:
                with self._neo4j.session() as session:
                    for subj, rel, obj in triples:
                        session.run(
                            "MERGE (a:Entity {name: $subj}) "
                            "MERGE (b:Entity {name: $obj}) "
                            "MERGE (a)-[r:" + rel + " {doc: $doc}]->(b)",
                            subj=subj, obj=obj, doc=doc_name,
                        )
            except Exception:
                pass

    def neighbours(self, entity: str) -> list[str]:
        """Return human-readable relation paths for an entity."""
        entity_lower = entity.lower()
        results: list[str] = []

        # Local graph
        for rel, obj in self._local.get(entity_lower, [])[:5]:
            results.append(f"{entity} --[{rel}]--> {obj}")

        # Neo4j
        if self._neo4j:
            try:
                with self._neo4j.session() as session:
                    cypher = (
                        "MATCH (a:Entity {name: $name})-[r]->(b:Entity) "
                        "RETURN type(r) AS rel, b.name AS obj LIMIT 5"
                    )
                    for rec in session.run(cypher, name=entity):
                        results.append(f"{entity} --[{rec['rel']}]--> {rec['obj']}")
            except Exception:
                pass

        return results


# ── Demo Corpus ───────────────────────────────────────────────────────────────

DEMO_CORPUS: list[dict] = [
    {
        "id": "demo-001",
        "name": "RAG-Lewis2020.txt",
        "text": (
            "Retrieval-Augmented Generation (RAG) combines parametric memory of large language models "
            "with non-parametric memory through dense passage retrieval. RAG uses a DPR retriever to "
            "fetch relevant passages, then conditions a seq2seq generator on retrieved content. "
            "RAG outperforms purely parametric models on open-domain QA benchmarks including Natural "
            "Questions and TriviaQA. The model achieves state-of-the-art performance while providing "
            "interpretable evidence through retrieved passages. RAG enables knowledge-intensive NLP "
            "tasks without expensive retraining by updating only the non-parametric memory component. "
            "Experiments show RAG generates more specific, factual and diverse responses compared to "
            "purely generative baselines on knowledge-intensive tasks."
        ),
    },
    {
        "id": "demo-002",
        "name": "RAPTOR-Sarthi2024.txt",
        "text": (
            "RAPTOR introduces recursive abstractive processing for tree-organized retrieval. "
            "The system clusters text chunks using Gaussian Mixture Models and generates abstractive "
            "summaries at each cluster level, building a hierarchical tree index. RAPTOR retrieval "
            "queries nodes at multiple abstraction levels, enabling both fine-grained and broad "
            "context retrieval. On QASPER and QuALITY benchmarks, RAPTOR improves performance "
            "over standard RAG by 20% on multi-hop questions requiring global context understanding. "
            "The hierarchical structure allows efficient navigation from document-level summaries "
            "down to paragraph-level evidence, addressing the limitation of flat chunk retrieval "
            "in standard RAG systems."
        ),
    },
    {
        "id": "demo-003",
        "name": "HippoRAG-Gutierrez2025.txt",
        "text": (
            "HippoRAG is inspired by the hippocampal indexing theory of human long-term memory. "
            "It uses OpenIE to extract knowledge graph triples from documents, stores them in a "
            "graph structure, and applies Personalized PageRank for multi-hop retrieval. "
            "The PPR score is computed as pi = alpha * eq + (1 - alpha) * pi * A, where eq is "
            "the query seed vector and A is the adjacency matrix. HippoRAG enables complex "
            "multi-hop question answering by traversing relation paths across multiple documents. "
            "Evaluation on MuSiQue and 2WikiMultiHopQA shows HippoRAG improves F1 by 10-15 points "
            "over standard RAG and ColBERT-based retrieval. The system integrates Sentence Transformers "
            "for semantic entity matching during graph traversal."
        ),
    },
    {
        "id": "demo-004",
        "name": "BioASQ-Nentidis2025.txt",
        "text": (
            "BioASQ 2025 is the 13th edition of the biomedical semantic indexing and question answering "
            "challenge. Task B evaluates systems on yes/no, factoid, list, and summary biomedical questions "
            "using PubMed abstracts as the evidence corpus. The 2025 challenge introduces a new track for "
            "multi-document summarization and citation-aware answer generation. Participating systems must "
            "retrieve relevant PubMed articles and generate both exact and ideal answers. Evaluation metrics "
            "include Mean Average Precision for document retrieval and F1-score for exact answers. "
            "Top systems in 2025 used hybrid retrieval combining dense bi-encoders with BM25, combined "
            "with instruction-tuned generative models for answer synthesis. BioASQ serves as the primary "
            "benchmark for GraphMind evaluation on biomedical question answering tasks."
        ),
    },
    {
        "id": "demo-005",
        "name": "AgenticRAG-Suresh2026.txt",
        "text": (
            "Agentic RAG decomposes monolithic retrieval-generation into a multi-agent pipeline with "
            "specialized roles: planner, retriever, reranker, generator, and verifier agents. "
            "The planner agent uses chain-of-thought reasoning to decompose complex questions into "
            "targeted sub-queries. The retriever agent performs hybrid search combining dense vectors "
            "with BM25 lexical matching. The verifier agent cross-checks generated claims against "
            "retrieved evidence using natural language inference. Agentic RAG reduces hallucination "
            "rates by 35% compared to single-pass RAG on scientific QA benchmarks. The modular "
            "architecture enables independent scaling and upgrading of individual agent components "
            "without disrupting the overall pipeline. Agent coordination uses structured JSON message "
            "passing for auditability and debugging."
        ),
    },
]


# ── Main Engine ───────────────────────────────────────────────────────────────

class GraphMindEngine:
    """Top-level engine: ingestion → indexing → retrieval → agentic QA."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._docs_file = data_dir / "documents.json"
        self._index_file = data_dir / "index.json"

        self.documents: dict[str, dict] = {}
        self.index = VectorIndex()
        self.graph = KnowledgeGraph()
        self.models = ModelProvider()
        self.orchestrator = GraphMindOrchestrator(
            models=self.models,
            retrieve=self._retrieve,
            graph_context=self.graph.neighbours,
        )

        self._load_state()
        if not self.documents:
            self._seed_demo_corpus()

    # ── persistence ───────────────────────────────────────────────────────

    def _load_state(self) -> None:
        if self._docs_file.exists():
            self.documents = json.loads(self._docs_file.read_text(encoding="utf-8"))
        self.index.load(self._index_file)

    def _save_state(self) -> None:
        self._docs_file.write_text(
            json.dumps(self.documents, ensure_ascii=False), encoding="utf-8"
        )
        self.index.save(self._index_file)

    # ── demo seeding ──────────────────────────────────────────────────────

    def _seed_demo_corpus(self) -> None:
        for entry in DEMO_CORPUS:
            self._ingest_text(
                doc_id=entry["id"],
                name=entry["name"],
                text=entry["text"],
                page_count=1,
            )
        self._save_state()

    # ── ingestion ─────────────────────────────────────────────────────────

    def _ingest_text(
        self,
        doc_id: str,
        name: str,
        text: str,
        page_count: int = 1,
    ) -> None:
        chunks = chunk_text(doc_id, name, text)
        # Apply dense embeddings if provider supports it
        for chunk in chunks:
            dense = self.models.embed(chunk.text)
            if dense:
                chunk.embedding = {f"dense_{i}": v for i, v in enumerate(dense)}
        self.index.add(chunks)
        self.graph.add_document(doc_id, name, text)
        self.documents[doc_id] = {
            "id": doc_id,
            "name": name,
            "page_count": page_count,
            "chunk_count": len(chunks),
            "demo": doc_id.startswith("demo-"),
        }

    def ingest(self, name: str, content: bytes, content_type: str) -> dict:
        """Ingest a PDF, TXT, or Markdown file."""
        doc_id = str(uuid.uuid4())
        text = ""
        page_count = 1

        if content_type == "application/pdf" or name.lower().endswith(".pdf"):
            text, page_count = self._extract_pdf(content)
        elif content_type in ("text/plain", "text/markdown") or name.lower().endswith((".txt", ".md")):
            text = content.decode("utf-8", errors="replace")
        else:
            text = content.decode("utf-8", errors="replace")

        if not text.strip():
            return {"error": "Could not extract text from the uploaded file."}

        self._ingest_text(doc_id, name, text, page_count)
        self._save_state()
        return self.documents[doc_id]

    def _extract_pdf(self, content: bytes) -> tuple[str, int]:
        """Extract text from PDF bytes using pypdf."""
        pages: list[str] = []
        try:
            from io import BytesIO
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(BytesIO(content))
            for page in reader.pages:
                extracted = page.extract_text() or ""
                pages.append(extracted)
        except ImportError:
            return content.decode("utf-8", errors="replace"), 1
        except Exception:
            return "", 0
        return "\n\n".join(pages), len(pages)

    def delete_document(self, doc_id: str) -> bool:
        if doc_id not in self.documents:
            return False
        self.documents.pop(doc_id)
        self.index.chunks = [c for c in self.index.chunks if c.document_id != doc_id]
        if self.index.chunks:
            self.index.build(self.index.chunks)
        self._save_state()
        return True

    # ── retrieval ────────────────────────────────────────────────────────

    def _retrieve(self, query: str, k: int = 6) -> list[dict]:
        results = self.index.search(query, k)
        return [
            {
                "chunk_id": c.id,
                "document_id": c.document_id,
                "document_name": c.document_name,
                "text": c.text,
                "page": c.page,
                "section": c.section,
                "score": round(score, 4),
                "citation": c.citation(),
            }
            for c, score in results
        ]

    # ── QA ────────────────────────────────────────────────────────────────

    def ask(
        self,
        question: str,
        limit: int = 6,
        document_id: str | None = None,
    ) -> dict:
        """Run the full agentic pipeline and return a structured response."""
        return self.orchestrator.run(question, limit=limit, document_id=document_id)
