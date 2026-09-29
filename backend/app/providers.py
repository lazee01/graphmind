"""Optional model adapters with explicit, dependency-safe local fallbacks."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen


class ModelProvider:
    def __init__(self) -> None:
        self.name = os.getenv("GRAPHMIND_MODEL_PROVIDER", "local").lower()
        self.slots = [slot.strip().lower() for slot in os.getenv("GRAPHMIND_PROVIDER_SLOTS", self.name).split(",") if slot.strip()][:5] or ["local"]
        self.embedding_model = os.getenv("GRAPHMIND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.generation_model = os.getenv("GRAPHMIND_GENERATION_MODEL", "llama-3.3-70b-versatile")
        self.gemini_model = os.getenv("GRAPHMIND_GEMINI_MODEL", "gemini-2.0-flash")
        self._embedder: Any = None
        self._generator: Any = None

    def _api_key(self, provider: str | None = None) -> str:
        selected = (provider or self.name).lower()
        if selected == "huggingface":
            return (
                os.getenv("GRAPHMIND_HUGGINGFACE_API_KEY")
                or os.getenv("HUGGING_FACE_HUB_TOKEN")
                or os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
            )
        return (
            os.getenv(f"GRAPHMIND_{selected.upper()}_API_KEY")
            or os.getenv("GRAPHMIND_LLM_API_KEY", "")
        )

    def _api_url(self, provider: str | None = None) -> str | None:
        selected = (provider or self.name).lower()
        if selected == "groq":
            return os.getenv("GRAPHMIND_GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
        if selected == "gemini":
            return f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent"
        return os.getenv("GRAPHMIND_LLM_API_URL")

    def status(self) -> dict[str, Any]:
        configured = self.name != "local"
        has_key = bool(self._api_key()) or any(bool(self._api_key(s)) for s in self.slots if s != "local")
        return {
            "provider": self.name,
            "embedding_model": self.embedding_model if configured else None,
            "generation_model": self.generation_model if configured else None,
            "active": bool(self._embedder or self._generator or has_key) if configured else True,
            "fallback": "tfidf-and-extractive-local",
            "slots": [{"name": slot, "configured": slot == "local" or bool(self._api_key(slot))} for slot in self.slots],
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

    def _call_openai_compatible(self, provider: str, prompt: str) -> str | None:
        url = self._api_url(provider)
        key = self._api_key(provider)
        if not url or not key:
            return None
        body = {
            "model": self.generation_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 900,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GraphMind/1.0",
        }
        try:
            import httpx
            resp = httpx.post(url, json=body, headers=headers, timeout=30.0)
            if resp.status_code == 200:
                payload = resp.json()
                return str(payload["choices"][0]["message"]["content"]).strip()
        except Exception:
            pass
        try:
            request = Request(url, data=json.dumps(body).encode(), headers=headers)
            with urlopen(request, timeout=25) as response:
                payload = json.loads(response.read())
            return str(payload["choices"][0]["message"]["content"]).strip()
        except (KeyError, OSError, TimeoutError, json.JSONDecodeError):
            return None

    def _call_gemini(self, prompt: str) -> str | None:
        url = self._api_url("gemini")
        key = self._api_key("gemini")
        if not url or not key:
            return None
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 900},
        }
        try:
            import httpx
            resp = httpx.post(f"{url}?key={key}", json=body, timeout=30.0)
            if resp.status_code == 200:
                payload = resp.json()
                return str(payload["candidates"][0]["content"]["parts"][0]["text"]).strip()
        except Exception:
            pass
        try:
            request = Request(
                f"{url}?key={key}",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            )
            with urlopen(request, timeout=25) as response:
                payload = json.loads(response.read())
            return str(payload["candidates"][0]["content"]["parts"][0]["text"]).strip()
        except (KeyError, IndexError, OSError, TimeoutError, json.JSONDecodeError):
            return None

    def generate(self, prompt: str) -> str | None:
        if self.name == "local":
            return None
        chain = [self.name] + [s for s in self.slots if s != self.name]
        for slot in chain:
            if slot in {"huggingface", "sentence-transformers"}:
                try:
                    result = self._load_generator()(prompt, max_new_tokens=220, do_sample=False)
                    out = str(result[0].get("generated_text") or result[0].get("text", "")).strip()
                    if out:
                        return out
                except (ImportError, OSError, RuntimeError):
                    continue
            elif slot in {"openai", "openai-compatible", "groq"}:
                out = self._call_openai_compatible(slot, prompt)
                if out:
                    return out
            elif slot == "gemini":
                out = self._call_gemini(prompt)
                if out:
                    return out
        return None

    def summarize(self, text: str) -> str | None:
        return self.generate(f"Summarize this scientific passage in two concise sentences:\n{text}")

    def plan(self, question: str) -> dict[str, Any] | None:
        q_type = "comparative" if ("compare" in question.lower() or "difference" in question.lower()) else "factoid"
        result = self.generate(
            f'Return ONLY valid JSON with keys "question_type", "sub_queries" (list of strings), and "entities" (list of strings) for this literature question: {question}'
        )
        if not result:
            return None
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.strip())
            parsed = json.loads(cleaned)
            return {
                "question_type": parsed.get("question_type", q_type),
                "sub_queries": parsed.get("sub_queries", [question]),
                "entities": parsed.get("entities", []),
            }
        except json.JSONDecodeError:
            return None

    def verify(self, answer: str, evidence: list[dict]) -> dict[str, Any] | None:
        if not evidence:
            return {"supported": False, "reason": "No retrieved evidence"}
        result = self.generate(
            f'Is this answer supported by the evidence? Return ONLY valid JSON with keys "supported" (boolean) and "reason" (string).\nAnswer: {answer}\nEvidence: {" ".join(item["text"] for item in evidence[:3])}'
        )
        if not result:
            return None
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.strip())
            return json.loads(cleaned)
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
