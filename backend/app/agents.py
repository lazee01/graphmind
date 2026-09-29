"""Provider-agnostic GraphMind agent coordination.

Five agents form a pipeline:
  Planner        – decomposes the question into targeted sub-queries
  Retriever      – fetches evidence chunks (vector + lexical hybrid)
  GraphReasoner  – walks the knowledge graph for multi-hop paths
  Verifier       – cross-checks the candidate answer against evidence
  Generator      – synthesises the final cited answer

Agents exchange AgentMessage objects (JSON-safe dicts) so any provider
(local / HuggingFace / Groq) shares one auditable execution contract.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentMessage:
    agent: str
    kind: str  # 'plan' | 'evidence' | 'graph' | 'verification' | 'answer'
    payload: dict[str, Any]


# ── Planner ───────────────────────────────────────────────────────────────────

class PlannerAgent:
    """Decomposes a complex question into focused sub-queries."""

    def __init__(self, models: Any) -> None:
        self.models = models

    def plan(self, question: str) -> list[str]:
        """Return a list of sub-query strings."""
        prompt = (
            "You are a scientific research query planner.\n"
            f"Decompose this question into 2-4 focused sub-queries for retrieval:\n"
            f"Question: {question}\n"
            "Return each sub-query on a new line, no numbering."
        )
        result = self.models.generate(prompt, max_tokens=150)
        if result:
            lines = [l.strip().lstrip("-•123456789. ") for l in result.splitlines() if l.strip()]
            subqueries = [l for l in lines if len(l) > 8][:4]
            if subqueries:
                return subqueries

        # Local fallback: extract key noun phrases as sub-queries
        words = question.lower().split()
        # Strip common question words
        stop = {"what", "how", "why", "when", "where", "which", "who", "is", "are", "does", "do", "the", "a", "an"}
        keywords = [w for w in words if w not in stop and len(w) > 3]
        # Generate sub-queries by keyword clusters
        if len(keywords) >= 4:
            mid = len(keywords) // 2
            return [
                question,
                " ".join(keywords[:mid]),
                " ".join(keywords[mid:]),
            ]
        return [question]


# ── Retriever ─────────────────────────────────────────────────────────────────

class RetrieverAgent:
    """Fetches ranked evidence chunks from the vector + lexical index."""

    def __init__(self, retrieve_fn: Callable[[str, int], list[dict]]) -> None:
        self._retrieve = retrieve_fn

    def retrieve(self, subqueries: list[str], limit: int = 6) -> list[dict]:
        """Retrieve and deduplicate evidence across all sub-queries."""
        seen: set[str] = set()
        results: list[dict] = []
        per_query = max(2, limit // len(subqueries))
        for q in subqueries:
            for chunk in self._retrieve(q, per_query + 2):
                cid = chunk.get("chunk_id", "")
                if cid not in seen:
                    seen.add(cid)
                    results.append(chunk)
        # Sort by score descending, cap at limit
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return results[:limit]


# ── GraphReasoner ─────────────────────────────────────────────────────────────

class GraphReasoningAgent:
    """Walks the knowledge graph to discover multi-hop relational context."""

    def __init__(self, graph_context_fn: Callable[[str], list[str]], models: Any) -> None:
        self._graph_context = graph_context_fn
        self.models = models

    def reason(self, question: str, entities: list[str]) -> list[str]:
        """Return a list of discovered relation paths as human-readable strings."""
        paths: list[str] = []
        for entity in entities[:5]:
            neighbours = self._graph_context(entity)
            paths.extend(neighbours)
        return list(dict.fromkeys(paths))[:10]  # deduplicated, max 10


# ── Verifier ──────────────────────────────────────────────────────────────────

class VerifierAgent:
    """Cross-checks a candidate answer against retrieved evidence."""

    def __init__(self, models: Any) -> None:
        self.models = models

    def verify(self, answer: str, evidence: list[dict]) -> dict[str, Any]:
        """
        Returns:
            verified  – bool: True if the answer is well-supported
            confidence – float [0, 1]
            warnings  – list of unsupported claims
        """
        if not evidence:
            return {"verified": False, "confidence": 0.1, "warnings": ["No evidence retrieved"]}

        # Build evidence corpus
        corpus = " ".join(e.get("text", "") for e in evidence).lower()
        answer_sentences = re.split(r"(?<=[.!?])\s+", answer.strip())

        supported = 0
        warnings: list[str] = []

        for sentence in answer_sentences:
            if len(sentence.split()) < 5:
                continue
            # Check if key nouns from the sentence appear in the evidence
            nouns = re.findall(r"\b[A-Za-z][a-z]{3,}\b", sentence)
            noun_hits = sum(1 for n in nouns if n.lower() in corpus)
            ratio = noun_hits / max(len(nouns), 1)
            if ratio >= 0.4:
                supported += 1
            else:
                snippet = sentence[:80] + "..." if len(sentence) > 80 else sentence
                warnings.append(f"Low evidence support: '{snippet}'")

        total = max(len([s for s in answer_sentences if len(s.split()) >= 5]), 1)
        confidence = min(0.95, 0.3 + 0.65 * (supported / total))

        return {
            "verified": confidence >= 0.45,
            "confidence": round(confidence, 3),
            "warnings": warnings[:3],
        }


# ── Generator ─────────────────────────────────────────────────────────────────

class GeneratorAgent:
    """Synthesises a final, cited answer from verified evidence."""

    def __init__(self, models: Any) -> None:
        self.models = models

    def generate(
        self,
        question: str,
        evidence: list[dict],
        graph_paths: list[str],
    ) -> str:
        """Generate a grounded answer with inline citation markers."""
        if not evidence:
            return "I could not find sufficient evidence in the indexed documents to answer this question."

        # Build context block
        context_parts: list[str] = []
        for i, e in enumerate(evidence[:6], 1):
            citation = e.get("citation", f"[{i}]")
            text = e.get("text", "")[:400]
            context_parts.append(f"[{i}] {citation}: {text}")

        context = "\n\n".join(context_parts)
        graph_hint = ""
        if graph_paths:
            graph_hint = "\n\nRelational context:\n" + "\n".join(f"• {p}" for p in graph_paths[:5])

        prompt = (
            f"You are a scientific literature expert. Answer the question using ONLY the provided evidence.\n"
            f"Cite sources with their reference numbers [1], [2], etc.\n\n"
            f"Question: {question}\n\n"
            f"Evidence:\n{context}{graph_hint}\n\n"
            f"Answer:"
        )

        result = self.models.generate(prompt, max_tokens=400)
        if result:
            return result

        # Local extractive fallback: pick top 3 evidence sentences most relevant to query
        query_words = set(re.findall(r"[a-z]{4,}", question.lower()))
        best: list[tuple[float, str, str]] = []

        for i, e in enumerate(evidence[:5], 1):
            text = e.get("text", "")
            citation = e.get("citation", f"source {i}")
            sentences = re.split(r"(?<=[.!?])\s+", text)
            for sent in sentences:
                words = set(re.findall(r"[a-z]{4,}", sent.lower()))
                overlap = len(words & query_words)
                if overlap > 0:
                    best.append((overlap, sent.strip(), f"[{i}]"))

        best.sort(reverse=True)
        if best:
            parts = [f"{sent} {ref}" for _, sent, ref in best[:3]]
            return " ".join(parts)

        return evidence[0].get("text", "")[:500] + " [1]"


# ── Orchestrator ──────────────────────────────────────────────────────────────

class GraphMindOrchestrator:
    """Coordinates the five-agent pipeline for a single query."""

    def __init__(
        self,
        models: Any,
        retrieve: Callable[[str, int], list[dict]],
        graph_context: Callable[[str], list[str]],
    ) -> None:
        self.models = models
        self.planner = PlannerAgent(models)
        self.retriever = RetrieverAgent(retrieve)
        self.graph_reasoner = GraphReasoningAgent(graph_context, models)
        self.verifier = VerifierAgent(models)
        self.generator = GeneratorAgent(models)

    def run(
        self,
        question: str,
        limit: int = 6,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute full pipeline and return structured result."""
        trace: list[dict] = []

        # 1. Plan
        subqueries = self.planner.plan(question)
        trace.append({"agent": "planner", "output": subqueries})

        # 2. Retrieve
        evidence = self.retriever.retrieve(subqueries, limit)
        # Filter by document_id if specified
        if document_id:
            evidence = [e for e in evidence if e.get("document_id") == document_id] or evidence
        trace.append({"agent": "retriever", "chunks_found": len(evidence)})

        # 3. Graph reasoning
        entities = self.models.extract_entities(question)
        graph_paths = self.graph_reasoner.reason(question, entities)
        trace.append({"agent": "graph_reasoner", "paths_found": len(graph_paths)})

        # 4. Generate
        answer = self.generator.generate(question, evidence, graph_paths)
        trace.append({"agent": "generator", "answer_length": len(answer)})

        # 5. Verify
        verification = self.verifier.verify(answer, evidence)
        trace.append({"agent": "verifier", "result": verification})

        # Build citations list
        citations = []
        for i, e in enumerate(evidence, 1):
            citations.append({
                "ref": i,
                "citation": e.get("citation", ""),
                "document_id": e.get("document_id", ""),
                "document_name": e.get("document_name", ""),
                "page": e.get("page"),
                "section": e.get("section", ""),
                "chunk_id": e.get("chunk_id", ""),
            })

        return {
            "answer": answer,
            "subqueries": subqueries,
            "evidence": evidence,
            "citations": citations,
            "graph_paths": graph_paths,
            "confidence": verification["confidence"],
            "verified": verification["verified"],
            "warnings": verification.get("warnings", []),
            "agent_trace": trace,
        }

    def status(self) -> dict[str, Any]:
        provider = self.models.status()
        mode = "model" if provider["active"] and provider["provider"] != "local" else "local"
        return {
            "agents": [
                {"name": "planner", "mode": mode},
                {"name": "retriever", "mode": "hybrid-tfidf"},
                {"name": "graph_reasoner", "mode": "local-regex"},
                {"name": "verifier", "mode": "local-overlap"},
                {"name": "generator", "mode": mode},
            ]
        }
