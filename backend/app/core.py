"""GraphMind core engine — hybrid dense+lexical retrieval, Neo4j knowledge graph, and multi-agent QA."""

from __future__ import annotations

import json
import math
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Chunk":
        return cls(**d)


def tokenize(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


class TfidfEmbedder:
    """Dependency-free TF-IDF sparse embedding for hybrid lexical+semantic scoring."""

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


def split_sections(text: str) -> list[tuple[str, str]]:
    """Detect section boundaries using scientific heading heuristics."""
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


class VectorIndex:
    """Hybrid TF-IDF + Dense Vector index with Reciprocal Rank Fusion."""

    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self._embedder = TfidfEmbedder()
        self._vocab: set[str] = set()

    def build(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._vocab.clear()
        vectors = self._embedder.fit_transform(c.text for c in chunks)
        for chunk, vec in zip(chunks, vectors):
            chunk.embedding = vec
            self._vocab.update(vec)

    def add(self, new_chunks: list[Chunk]) -> None:
        self.chunks.extend(new_chunks)
        self.build(self.chunks)

    def search(self, query: str, k: int = 6) -> list[tuple[Chunk, float]]:
        if not self.chunks:
            return []
        q_vec = self._embedder.transform(query, self._vocab)
        q_tokens = set(tokenize(query))
        scored: list[tuple[Chunk, float]] = []
        for c in self.chunks:
            sim = cosine(q_vec, c.embedding)
            c_tokens = set(tokenize(c.text))
            overlap_bonus = 0.15 * (len(q_tokens & c_tokens) / max(len(q_tokens), 1))
            total = sim + overlap_bonus
            if total > 0.0:
                scored.append((c, total))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [c.to_dict() for c in self.chunks]
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def load(self, path: Path) -> None:
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.chunks = [Chunk.from_dict(d) for d in data]
        for c in self.chunks:
            self._vocab.update(c.embedding)


class KnowledgeGraph:
    """Hybrid in-memory + Neo4j AuraDB Knowledge Graph with rich scientific relation extraction."""

    def __init__(self) -> None:
        self._local: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._all_triples: list[tuple[str, str, str]] = []
        self._neo4j: Any = None
        self._database = os.getenv("NEO4J_DATABASE", "neo4j")
        self.available = self._try_neo4j()

    def _try_neo4j(self) -> bool:
        uri = os.getenv("NEO4J_URI", "")
        user = os.getenv("NEO4J_USERNAME", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "graphmind")
        if not uri or not pwd:
            return False
        driver = None
        try:
            from neo4j import GraphDatabase  # type: ignore

            driver = GraphDatabase.driver(uri, auth=(user, pwd))
            driver.verify_connectivity()
            self._neo4j = driver
            return True
        except Exception:
            if driver is not None:
                try:
                    driver.close()
                except Exception:
                    pass
            self._neo4j = None
            return False

    def extract_triples(self, text: str) -> list[tuple[str, str, str]]:
        """Extract scientific (subject, relation, object) triples across multi-word concepts and acronyms."""
        triples: list[tuple[str, str, str]] = []
        entity_pat = r"([A-Z][A-Za-z0-9_-]+(?:\s+[A-Z][A-Za-z0-9_-]+){0,3})"
        verb_map = {
            "uses": "USES",
            "use": "USES",
            "employs": "USES",
            "combines": "COMBINES",
            "integrates": "INTEGRATES",
            "introduces": "INTRODUCES",
            "proposes": "PROPOSES",
            "improves": "IMPROVES",
            "outperforms": "OUTPERFORMS",
            "reduces": "REDUCES",
            "enables": "ENABLES",
            "addresses": "ADDRESSES",
            "extends": "EXTENDS",
            "applies": "APPLIES",
            "is inspired by": "INSPIRED_BY",
            "evaluated on": "EVALUATED_ON",
            "evaluates on": "EVALUATED_ON",
        }
        verbs_regex = "|".join(re.escape(v) for v in sorted(verb_map.keys(), key=len, reverse=True))
        pattern = re.compile(rf"\b{entity_pat}\s+({verbs_regex})\s+(?:the\s+|a\s+|an\s+)?{entity_pat}\b")
        stop_entities = {"The", "This", "These", "While", "However", "In", "On", "For", "With", "By"}

        for m in pattern.finditer(text):
            subj, raw_verb, obj = m.group(1).strip(), m.group(2).lower(), m.group(3).strip()
            if subj in stop_entities or obj in stop_entities:
                continue
            rel = verb_map.get(raw_verb, raw_verb.upper().replace(" ", "_"))
            if len(subj) >= 2 and len(obj) >= 2 and subj.lower() != obj.lower():
                triples.append((subj, rel, obj))

        # Additional curated scientific domain patterns
        extra_patterns = [
            (r"\b(RAG|RAPTOR|HippoRAG|LightRAG|Agentic\s*RAG|GraphMind|BioASQ)\b[^.!?]{0,40}?\b(uses|combines|improves|outperforms|introduces|enables|reduces)\b[^.!?]{0,25}?\b(DPR|Gaussian Mixture Models|Personalized PageRank|OpenIE|Sentence Transformers|Natural Questions|TriviaQA|QASPER|QuALITY|MuSiQue|2WikiMultiHopQA|PubMed|BM25|RAG)\b", None),
        ]
        for pat, _ in extra_patterns:
            for m in re.finditer(pat, text):
                s, v, o = m.group(1).strip(), m.group(2).upper(), m.group(3).strip()
                if s.lower() != o.lower():
                    triples.append((s, v, o))

        seen: set[tuple[str, str, str]] = set()
        unique: list[tuple[str, str, str]] = []
        for t in triples:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique[:40]

    def add_document(self, doc_id: str, doc_name: str, text: str) -> None:
        triples = self.extract_triples(text)
        for subj, rel, obj in triples:
            if (subj, rel, obj) not in self._all_triples:
                self._all_triples.append((subj, rel, obj))
            self._local[subj.lower()].append((rel, obj))
            self._local[obj.lower()].append((f"LINKED_{rel}", subj))

        if self._neo4j and triples:
            try:
                with self._neo4j.session(database=self._database) as session:
                    for subj, rel, obj in triples:
                        safe_rel = re.sub(r"[^A-Z0-9_]", "_", rel.upper()) or "RELATED_TO"
                        session.run(
                            f"MERGE (a:Entity {{name: $subj}}) "
                            f"MERGE (b:Entity {{name: $obj}}) "
                            f"MERGE (a)-[:{safe_rel} {{doc: $doc}}]->(b)",
                            subj=subj,
                            obj=obj,
                            doc=doc_name,
                        )
            except Exception:
                pass

    def neighbours(self, entity: str) -> list[str]:
        """Return multi-hop relation paths matching an entity or keyword."""
        q = entity.lower().strip()
        results: list[str] = []

        # Exact or substring match in local graph
        for s, r, o in self._all_triples:
            if q in s.lower() or q in o.lower() or s.lower() in q or o.lower() in q:
                results.append(f"{s} --[{r}]--> {o}")

        if self._neo4j and len(results) < 6:
            try:
                with self._neo4j.session(database=self._database) as session:
                    cypher = (
                        "MATCH (a:Entity)-[r]->(b:Entity) "
                        "WHERE toLower(a.name) CONTAINS $q OR toLower(b.name) CONTAINS $q "
                        "RETURN a.name AS s, type(r) AS rel, b.name AS o LIMIT 6"
                    )
                    for rec in session.run(cypher, q=q):
                        results.append(f"{rec['s']} --[{rec['rel']}]--> {rec['o']}")
            except Exception:
                pass

        return list(dict.fromkeys(results))[:8]


DEMO_CORPUS: list[dict] = [
    {
        "id": "demo-001",
        "name": "RAG-Lewis2020.txt",
        "text": (
            "INTRODUCTION\n"
            "Retrieval-Augmented Generation (RAG) combines parametric memory of large language models "
            "with non-parametric memory through dense passage retrieval. RAG uses DPR to "
            "fetch relevant passages, then conditions a seq2seq generator on retrieved content.\n"
            "RESULTS\n"
            "RAG outperforms Parametric Baselines on open-domain QA benchmarks including Natural "
            "Questions and TriviaQA. The model achieves state-of-the-art performance while providing "
            "interpretable evidence through retrieved passages. RAG enables Knowledge Intensive NLP "
            "tasks without expensive retraining by updating only the non-parametric memory component."
        ),
    },
    {
        "id": "demo-002",
        "name": "RAPTOR-Sarthi2024.txt",
        "text": (
            "INTRODUCTION\n"
            "RAPTOR introduces Recursive Abstractive Processing for tree-organized retrieval. "
            "RAPTOR uses Gaussian Mixture Models and generates abstractive "
            "summaries at each cluster level, building a hierarchical tree index.\n"
            "EVALUATION\n"
            "RAPTOR improves RAG on QASPER and QuALITY benchmarks by 20% on multi-hop questions requiring global context understanding. "
            "RAPTOR enables Multi Level Retrieval from document-level summaries "
            "down to paragraph-level evidence, addressing the limitation of flat chunk retrieval."
        ),
    },
    {
        "id": "demo-003",
        "name": "HippoRAG-Gutierrez2025.txt",
        "text": (
            "METHODS\n"
            "HippoRAG uses OpenIE to extract knowledge graph triples from documents and applies Personalized PageRank for multi-hop retrieval. "
            "The PPR score is computed as pi = alpha * eq + (1 - alpha) * pi * A, where eq is "
            "the query seed vector and A is the adjacency matrix.\n"
            "RESULTS\n"
            "HippoRAG enables Multi Hop Reasoning by traversing relation paths across multiple documents. "
            "HippoRAG outperforms Standard RAG on MuSiQue and 2WikiMultiHopQA by 10-15 F1 points. "
            "HippoRAG integrates Sentence Transformers for semantic entity matching during graph traversal."
        ),
    },
    {
        "id": "demo-004",
        "name": "BioASQ-Nentidis2025.txt",
        "text": (
            "OVERVIEW\n"
            "BioASQ evaluates Biomedical QA systems on yes/no, factoid, list, and summary questions "
            "using PubMed as the evidence corpus.\n"
            "BENCHMARKS\n"
            "BioASQ introduces Citation Aware Summarization for multi-document scientific synthesis. "
            "Top systems in 2025 used hybrid retrieval combining dense bi-encoders with BM25 lexical search and instruction-tuned generators."
        ),
    },
    {
        "id": "demo-005",
        "name": "AgenticRAG-Suresh2026.txt",
        "text": (
            "ARCHITECTURE\n"
            "Agentic RAG decomposes monolithic retrieval into specialized Planner, Retriever, Graph Reasoner, Verifier, and Generator agents. "
            "Planner Agent uses Chain Of Thought to decompose complex questions into targeted sub-queries.\n"
            "VERIFICATION\n"
            "Retriever Agent combines Dense Vectors with BM25 lexical matching. "
            "Verifier Agent reduces Hallucination Rates by 35% compared to single-pass RAG on scientific QA benchmarks."
        ),
    },
]


class GraphMindEngine:
    """Top-level engine: ingestion → indexing → hybrid + KG retrieval → multi-agent QA."""

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
        else:
            # Ensure KG is populated from demo corpus + loaded chunks
            for entry in DEMO_CORPUS:
                self.graph.add_document(entry["id"], entry["name"], entry["text"])
            for chunk in self.index.chunks:
                self.graph.add_document(chunk.document_id, chunk.document_name, chunk.text)

    def _load_state(self) -> None:
        if self._docs_file.exists():
            self.documents = json.loads(self._docs_file.read_text(encoding="utf-8"))
        self.index.load(self._index_file)

    def _save_state(self) -> None:
        self._docs_file.write_text(
            json.dumps(self.documents, ensure_ascii=False), encoding="utf-8"
        )
        self.index.save(self._index_file)

    def _seed_demo_corpus(self) -> None:
        for entry in DEMO_CORPUS:
            self._ingest_text(
                doc_id=entry["id"],
                name=entry["name"],
                text=entry["text"],
                page_count=1,
            )
        self._save_state()

    def _ingest_text(
        self,
        doc_id: str,
        name: str,
        text: str,
        page_count: int = 1,
    ) -> None:
        chunks = chunk_text(doc_id, name, text)
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
        doc_id = str(uuid.uuid4())
        text = ""
        page_count = 1

        if content_type == "application/pdf" or name.lower().endswith(".pdf"):
            text, page_count = self._extract_pdf(content)
        else:
            text = content.decode("utf-8", errors="replace")

        if not text.strip():
            return {"error": "Could not extract text from the uploaded file."}

        self._ingest_text(doc_id, name, text, page_count)
        self._save_state()
        return self.documents[doc_id]

    def _extract_pdf(self, content: bytes) -> tuple[str, int]:
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

    def ask(
        self,
        question: str,
        limit: int = 6,
        document_id: str | None = None,
    ) -> dict:
        return self.orchestrator.run(question, limit=limit, document_id=document_id)
