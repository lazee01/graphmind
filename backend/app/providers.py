"""Optional model adapters with explicit, dependency-safe local fallbacks."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.request import Request, urlopen


class ModelProvider:
    def __init__(self) -> None:
        self.name = os.getenv("GRAPHMIND_MODEL_PROVIDER", "local").lower()
        self.embedding_model = os.getenv("GRAPHMIND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.generation_model = os.getenv("GRAPHMIND_GENERATION_MODEL", "google/flan-t5-base")
        self._embedder: Any = None
        self._generator: Any = None

    def status(self) -> dict[str, Any]:
        configured = self.name != "local"
        return {
            "provider": self.name,
            "embedding_model": self.embedding_model if configured else None,
            "generation_model": self.generation_model if configured else None,
            "active": bool(self._embedder or self._generator) if configured else True,
            "fallback": "tfidf-and-extractive-local",
        }

    def _load_embedding_model(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        from sentence_transformers import SentenceTransformer
        self._embedder = SentenceTransformer(self.embedding_model)
        return self._embedder

    def embed(self, texts: list[str]) -> list[dict[str, float]] | None:
        if self.name not in {"sentence-transformers", "huggingface"}:
            return None
        try:
            vectors = self._load_embedding_model().encode(texts, normalize_embeddings=True)
            return [{str(index): float(value) for index, value in enumerate(vector)} for vector in vectors]
        except (ImportError, OSError, RuntimeError):
            return None

    def _load_generator(self) -> Any:
        if self._generator is not None:
            return self._generator
        from transformers import pipeline
        task = "text2text-generation" if "t5" in self.generation_model.lower() else "text-generation"
        self._generator = pipeline(task, model=self.generation_model)
        return self._generator

    def generate(self, prompt: str) -> str | None:
        if self.name == "local":
            return None
        if self.name in {"huggingface", "sentence-transformers"}:
            try:
                result = self._load_generator()(prompt, max_new_tokens=220, do_sample=False)
                return str(result[0].get("generated_text") or result[0].get("text", "")).strip()
            except (ImportError, OSError, RuntimeError):
                return None
        if self.name in {"openai", "openai-compatible"}:
            url = os.getenv("GRAPHMIND_LLM_API_URL")
            key = os.getenv("GRAPHMIND_LLM_API_KEY")
            if not url or not key:
                return None
            try:
                request = Request(url, data=json.dumps({"model": self.generation_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read())
                return str(payload["choices"][0]["message"]["content"]).strip()
            except (KeyError, OSError, TimeoutError, json.JSONDecodeError):
                return None
        return None

    def summarize(self, text: str) -> str | None:
        return self.generate(f"Summarize this scientific passage in two concise sentences:\n{text}")

    def plan(self, question: str) -> dict[str, Any] | None:
        result = self.generate(f"Return JSON with sub_queries and entities for this literature question: {question}")
        if not result:
            return None
        try:
            parsed = json.loads(result)
            return {"sub_queries": parsed.get("sub_queries", [question]), "entities": parsed.get("entities", [])}
        except json.JSONDecodeError:
            return None

    def verify(self, answer: str, evidence: list[dict]) -> dict[str, Any] | None:
        if not evidence:
            return {"supported": False, "reason": "No retrieved evidence"}
        result = self.generate(f"Is this answer supported by the evidence? Return JSON with supported and reason.\nAnswer: {answer}\nEvidence: {' '.join(item['text'] for item in evidence[:3])}")
        if not result:
            return None
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return None

    def entities(self, text: str) -> list[str] | None:
        if self.name != "huggingface":
            return None
        try:
            from transformers import pipeline
            ner = pipeline("token-classification", model=os.getenv("GRAPHMIND_NER_MODEL", "dslim/bert-base-NER"), aggregation_strategy="simple")
            return [str(item["word"]).lower() for item in ner(text) if float(item.get("score", 0)) >= 0.75]
        except (ImportError, OSError, RuntimeError):
            return None
