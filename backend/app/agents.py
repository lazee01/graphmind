"""Provider-agnostic GraphMind agent coordination.

Agents exchange JSON-shaped dictionaries so the local fallback, Hugging Face,
and OpenAI-compatible providers share one auditable execution contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class AgentMessage:
    agent: str
    kind: str
    payload: dict[str, Any]


class GraphMindOrchestrator:
    def __init__(self, models: Any, retrieve: Callable[[str, int], list[dict]], graph_context: Callable[[str], list[str]]) -> None:
        self.models = models
        self.retrieve = retrieve
        self.graph_context = graph_context

    def status(self) -> dict[str, Any]:
        provider = self.models.status()
        return {
            "agents": [
                {"name": "planner", "mode": "model" if provider["active"] and provider["provider"] != "local" else "local"},
                {"name": "retrieval", "mode": "hybrid-local"},
                {"name": "graph", "mode": "model-ner+local-graph" if provider["provider"] == "huggingface" else "local-graph"},
                {"name": "verifier", "mode": "model" if provider["active"] and provider["provider"] != "local" else "local"},
                {"name": "generator", "mode": "model" if provider["active"] and provider["provider"] != "local" else "extractive-local"},
            ],
            "provider": provider,
            "coordination": "plan→retrieve→graph→fuse→verify→generate",
        }

    def run(self, question: str, limit: int = 6) -> dict[str, Any]:
        plan = self.models.plan(question) or {"sub_queries": [question], "entities": []}
        queries = plan.get("sub_queries") or [question]
        evidence_by_id: dict[str, dict] = {}
        for query in queries[:3]:
            for item in self.retrieve(query, limit):
                evidence_by_id[item["id"]] = item
        evidence = sorted(evidence_by_id.values(), key=lambda item: item["score"], reverse=True)[:limit]
        return {
            "messages": [
                AgentMessage("planner", "plan", plan).__dict__,
                AgentMessage("retrieval", "evidence", {"count": len(evidence)}).__dict__,
                AgentMessage("graph", "context", {"items": self.graph_context(question)}).__dict__,
            ],
            "plan": plan,
            "evidence": evidence,
            "graph_context": self.graph_context(question),
        }
