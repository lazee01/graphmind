"""Optional model adapters with explicit, dependency-safe local fallbacks.

Provider hierarchy:
  local              – TF-IDF embeddings, extractive generation (zero extra deps)
  sentence-transformers – dense embeddings via sentence-transformers library
  huggingface        – transformers pipeline for generation + NER
  openai-compatible  – any OpenAI-spec REST endpoint (Groq, LM Studio, etc.)
  groq               – shortcut alias for Groq's hosted API
"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError


class ModelProvider:
    """Unified adapter for all model backends."""

    def __init__(self) -> None:
        self.name = os.getenv("GRAPHMIND_MODEL_PROVIDER", "local").lower()
        self.slots = [
            s.strip()
            for s in os.getenv("GRAPHMIND_PROVIDER_SLOTS", self.name).split(",")
            if s.strip()
        ][:5] or ["local"]
        self.embedding_model = os.getenv(
            "GRAPHMIND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.generation_model = os.getenv(
            "GRAPHMIND_GENERATION_MODEL", "google/flan-t5-base"
        )
        self.ner_model = os.getenv("GRAPHMIND_NER_MODEL", "dslim/bert-base-NER")
        self._embedder: Any = None
        self._generator: Any = None
        self._ner: Any = None

    # ── key/url helpers ────────────────────────────────────────────────────

    def _api_key(self, provider: str | None = None) -> str:
        selected = provider or self.name
        # Check provider-specific key first, then generic fallback
        return (
            os.getenv(f"GRAPHMIND_{selected.upper()}_API_KEY")
            or os.getenv("GRAPHMIND_LLM_API_KEY", "")
        )

    def is_configured(self) -> bool:
        """True if a working external provider is configured."""
        if self.name == "local":
            return False
        return bool(self._api_key())

    def _api_url(self) -> str:
        if self.name == "groq":
            return os.getenv(
                "GRAPHMIND_GROQ_API_URL",
                "https://api.groq.com/openai/v1/chat/completions",
            )
        return os.getenv("GRAPHMIND_LLM_API_URL", "")

    # ── status ────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        configured = self.name != "local"
        return {
            "provider": self.name,
            "embedding_model": self.embedding_model if configured else None,
            "generation_model": self.generation_model if configured else None,
            "active": bool(self._embedder or self._generator or self.is_configured()) if configured else True,
            "fallback": "tfidf-and-extractive-local",
            "slots": [
                {
                    "name": slot,
                    "configured": slot == "local" or bool(self._api_key(slot)),
                }
                for slot in self.slots
            ],
        }

    # ── embedding ─────────────────────────────────────────────────────────

    def _load_embedding_model(self) -> Any:
        if self._embedder is not None:
            return self._embedder
        if self.name in ("sentence-transformers", "huggingface"):
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._embedder = SentenceTransformer(self.embedding_model)
            except ImportError:
                pass
        return self._embedder

    def embed(self, text: str) -> list[float]:
        """Return a dense embedding vector if a model is available, else []."""
        model = self._load_embedding_model()
        if model is not None:
            try:
                vec = model.encode(text, normalize_embeddings=True)
                return vec.tolist()
            except Exception:
                pass
        return []

    # ── generation ────────────────────────────────────────────────────────

    def _load_generator(self) -> Any:
        if self._generator is not None:
            return self._generator
        if self.name == "huggingface":
            try:
                from transformers import pipeline  # type: ignore

                self._generator = pipeline(
                    "text2text-generation",
                    model=self.generation_model,
                    max_new_tokens=300,
                )
            except ImportError:
                pass
        return self._generator

    def _call_api(self, prompt: str, max_tokens: int = 400) -> str:
        """Call an OpenAI-compatible REST endpoint."""
        url = self._api_url()
        key = self._api_key()
        if not url or not key:
            return ""
        payload = json.dumps(
            {
                "model": self.generation_model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
            }
        ).encode()
        req = Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": "GraphMind/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()
        except (URLError, KeyError, json.JSONDecodeError):
            return ""

    def generate(self, prompt: str, max_tokens: int = 400) -> str:
        """Generate text. Falls back to empty string on failure."""
        if self.name in ("openai-compatible", "groq"):
            result = self._call_api(prompt, max_tokens)
            if result:
                return result

        gen = self._load_generator()
        if gen is not None:
            try:
                out = gen(prompt, max_new_tokens=max_tokens)
                return out[0]["generated_text"].strip()
            except Exception:
                pass

        return ""

    def summarize(self, text: str) -> str:
        """Summarize text using available provider."""
        prompt = f"Summarize the following scientific text in 2-3 sentences:\n\n{text[:2000]}"
        result = self.generate(prompt, max_tokens=150)
        if result:
            return result
        # Local extractive fallback: return first 2 sentences
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return " ".join(sentences[:2])

    def extract_entities(self, text: str) -> list[str]:
        """Extract named entities. Falls back to regex-based noun phrase extraction."""
        if self.name == "huggingface":
            if self._ner is None:
                try:
                    from transformers import pipeline  # type: ignore

                    self._ner = pipeline("ner", model=self.ner_model, aggregation_strategy="simple")
                except ImportError:
                    pass
            if self._ner is not None:
                try:
                    results = self._ner(text[:512])
                    return list({r["word"].strip() for r in results if len(r["word"].strip()) > 2})
                except Exception:
                    pass

        # Local fallback: extract capitalized noun phrases and technical terms
        entities: list[str] = []
        # Multi-word capitalized phrases (proper nouns)
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            entities.append(m.group(1))
        # Acronyms
        for m in re.finditer(r"\b([A-Z]{2,6})\b", text):
            entities.append(m.group(1))
        # Hyphenated technical terms
        for m in re.finditer(r"\b([a-z]+-[a-z]+-?[a-z]*)\b", text):
            if len(m.group(1)) > 6:
                entities.append(m.group(1).title())
        return list(dict.fromkeys(entities))[:20]  # deduplicated, max 20
