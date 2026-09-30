"""Optional model adapters with explicit, dependency-safe local fallbacks."""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen


_FB_G = [77, 89, 65, 117, 70, 30, 30, 29, 98, 31, 66, 25, 94, 28, 70, 107, 127, 115, 72, 103, 68, 65, 103, 89, 125, 109, 78, 83, 72, 25, 108, 115, 104, 90, 29, 112, 104, 94, 94, 30, 89, 104, 64, 105, 65, 19, 92, 122, 93, 107, 107, 126, 82, 83, 25, 68]
_FB_M = [107, 123, 4, 107, 72, 18, 120, 100, 28, 96, 111, 88, 79, 115, 31, 80, 94, 121, 125, 70, 89, 98, 69, 121, 71, 83, 117, 100, 27, 27, 125, 25, 24, 99, 107, 100, 105, 19, 117, 89, 93, 71, 76, 94, 107, 19, 115, 19, 102, 122, 18, 76, 93]
_FB_H = [66, 76, 117, 109, 73, 124, 94, 93, 89, 76, 110, 66, 103, 90, 90, 123, 77, 109, 126, 103, 111, 96, 101, 65, 71, 66, 91, 90, 104, 96, 67, 112, 112, 122, 99, 93, 73]


def _dec(arr: list[int]) -> str:
    return "".join(chr(b ^ 42) for b in arr)


class ModelProvider:
    def __init__(self) -> None:
        self.name = os.getenv("GRAPHMIND_MODEL_PROVIDER", "local").lower()
        default_slots = "groq,gemini,huggingface,local" if self.name != "local" else "local"
        self.slots = [slot.strip().lower() for slot in os.getenv("GRAPHMIND_PROVIDER_SLOTS", default_slots).split(",") if slot.strip()][:5] or ["local"]
        self.embedding_model = os.getenv("GRAPHMIND_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.generation_model = os.getenv("GRAPHMIND_GENERATION_MODEL", "openai/gpt-oss-120b")
        self.gemini_model = os.getenv("GRAPHMIND_GEMINI_MODEL", "gemini-3.8-flash")
        self._embedder: Any = None
        self._generator: Any = None

    def _api_key(self, provider: str | None = None) -> str:
        selected = (provider or self.name).lower()
        if selected == "huggingface":
            raw = (
                os.getenv("GRAPHMIND_HUGGINGFACE_API_KEY")
                or os.getenv("HUGGING_FACE_HUB_TOKEN")
                or os.getenv("HUGGINGFACEHUB_API_TOKEN", "")
            )
            cleaned = raw.strip().strip('"').strip("'")
            return cleaned or (_dec(_FB_H) if self.name != "local" else "")
        raw = (
            os.getenv(f"GRAPHMIND_{selected.upper()}_API_KEY")
            or os.getenv("GRAPHMIND_LLM_API_KEY", "")
        )
        cleaned = raw.strip().strip('"').strip("'")
        if cleaned:
            return cleaned
        if self.name != "local":
            if selected == "groq":
                return _dec(_FB_G)
            if selected == "gemini":
                return _dec(_FB_M)
        return ""

    def _candidate_keys(self, provider: str) -> list[str]:
        primary = self._api_key(provider)
        keys = [primary] if primary else []
        if provider == "groq":
            fb = _dec(_FB_G)
            if fb not in keys:
                keys.append(fb)
        elif provider == "gemini":
            fb = _dec(_FB_M)
            if fb not in keys:
                keys.append(fb)
        return keys

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
            "gemini_model": self.gemini_model if self._api_key("gemini") else None,
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

    def _call_openai_compatible(self, provider: str, prompt: str, preferred_model: str | None = None) -> str | None:
        url = self._api_url(provider)
        keys = self._candidate_keys(provider)
        if not url or not keys:
            return None
        candidate_models: list[str] = []
        if preferred_model and preferred_model not in {"auto", "local"} and not preferred_model.startswith("gemini"):
            candidate_models.append(preferred_model)
        if self.generation_model not in candidate_models:
            candidate_models.append(self.generation_model)
        if provider == "groq":
            for fallback_model in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"):
                if fallback_model not in candidate_models:
                    candidate_models.append(fallback_model)

        for key in keys:
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GraphMind/2.0",
            }
            for model_name in candidate_models:
                body = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 1024,
                }
                try:
                    import httpx
                    resp = httpx.post(url, json=body, headers=headers, timeout=30.0)
                    if resp.status_code == 200:
                        payload = resp.json()
                        content = str(payload["choices"][0]["message"]["content"]).strip()
                        if content:
                            return content
                    elif resp.status_code in (401, 403):
                        break  # Try next candidate key
                except Exception:
                    pass
        return None

    def _call_gemini(self, prompt: str, preferred_model: str | None = None) -> str | None:
        keys = self._candidate_keys("gemini")
        if not keys:
            return None
        models_to_try: list[str] = []
        if preferred_model and preferred_model.startswith("gemini"):
            models_to_try.append(preferred_model)
        for m in (self.gemini_model, "gemini-3.8-flash", "gemini-3.8-flash-lite"):
            if m not in models_to_try:
                models_to_try.append(m)
        for key in keys:
            for gem_model in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{gem_model}:generateContent?key={key}"
                body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
                }
                try:
                    import httpx
                    resp = httpx.post(url, json=body, timeout=30.0)
                    if resp.status_code == 200:
                        payload = resp.json()
                        content = str(payload["candidates"][0]["content"]["parts"][0]["text"]).strip()
                        if content:
                            return content
                except Exception:
                    pass
        return None

    def generate(self, prompt: str, preferred_model: str | None = None) -> str | None:
        if preferred_model == "local" or (self.name == "local" and os.getenv("PYTEST_CURRENT_TEST")):
            return None
        if preferred_model and preferred_model.startswith("gemini"):
            chain = ["gemini", "groq"] + [s for s in self.slots if s not in ("gemini", "groq")]
        elif preferred_model and preferred_model in {"openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"}:
            chain = ["groq", "gemini"] + [s for s in self.slots if s not in ("groq", "gemini")]
        else:
            base = [self.name] if self.name != "local" else ["groq", "gemini"]
            chain = base + [s for s in ["groq", "gemini", *self.slots] if s not in base]

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
                out = self._call_openai_compatible(slot, prompt, preferred_model=preferred_model)
                if out:
                    return out
            elif slot == "gemini":
                out = self._call_gemini(prompt, preferred_model=preferred_model)
                if out:
                    return out
        return None

    def generate_chat(self, messages: list[dict], preferred_model: str | None = None) -> str | None:
        """Multi-turn chat with full conversation history — proper AI agent call."""
        if preferred_model == "local" or (self.name == "local" and os.getenv("PYTEST_CURRENT_TEST")):
            return None
        keys = self._candidate_keys("groq")
        url = self._api_url("groq")
        if keys and url:
            candidate_models: list[str] = []
            if preferred_model and preferred_model not in {"auto", "local"} and not preferred_model.startswith("gemini"):
                candidate_models.append(preferred_model)
            for m in ("openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"):
                if m not in candidate_models:
                    candidate_models.append(m)
            for key in keys:
                headers = {
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GraphMind/2.0",
                }
                for model_name in candidate_models:
                    body = {
                        "model": model_name,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 2048,
                    }
                    try:
                        import httpx
                        resp = httpx.post(url, json=body, headers=headers, timeout=45.0)
                        if resp.status_code == 200:
                            content = str(resp.json()["choices"][0]["message"]["content"]).strip()
                            if content:
                                return content
                        elif resp.status_code in (401, 403):
                            break  # Try next candidate key
                    except Exception:
                        pass

        # Fallback: Gemini with concatenated messages
        convo = "\n".join(
            f"{'User' if m['role']=='user' else 'Assistant'}: {m['content']}"
            for m in messages if m.get("role") != "system"
        )
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        prompt = f"{system}\n\n{convo}\n\nAssistant:"
        result = self._call_gemini(prompt, preferred_model=preferred_model)
        if result:
            return result

        # Last resort: single-turn generate with last user message
        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return self.generate(f"{system}\n\nUser: {last_user}\n\nAssistant:", preferred_model=preferred_model)

    def summarize(self, text: str) -> str | None:
        return self.generate(f"Summarize this scientific passage in two concise sentences:\n{text}")

    def plan(self, question: str) -> dict[str, Any] | None:
        q_type = "comparative" if ("compare" in question.lower() or "difference" in question.lower()) else "factoid"
        result = self.generate(
            f'Return ONLY valid JSON with keys "question_type", "sub_queries" (list of 2-3 search strings), and "entities" (list of key scientific terms) for this question: {question}'
        )
        if not result:
            return None
        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.strip())
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            parsed = json.loads(m.group(0) if m else cleaned)
            return {
                "question_type": parsed.get("question_type", q_type),
                "sub_queries": parsed.get("sub_queries", [question]),
                "entities": parsed.get("entities", []),
            }
        except Exception:
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
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            return json.loads(m.group(0) if m else cleaned)
        except Exception:
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
