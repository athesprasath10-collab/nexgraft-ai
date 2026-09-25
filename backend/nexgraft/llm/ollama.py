"""Thin async client for the local Ollama HTTP API.

Only the endpoints NEXGRAFT uses are wrapped: /api/tags, /api/show, /api/ps,
/api/version, /api/chat (streaming + structured JSON) and /api/embed.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from ..config import settings


class OllamaError(RuntimeError):
    """Raised with a user-readable message when Ollama cannot serve a request."""


_EMBED_HINTS = ("embed", "bge", "minilm", "e5-", "gte-")
_VISION_HINTS = ("vl", "vision", "llava", "moondream", "bakllava", "minicpm-v", "gemma3")


@dataclass
class ModelInfo:
    name: str
    size: int = 0
    family: str = ""
    parameter_size: str = ""
    quantization: str = ""
    capabilities: list[str] = field(default_factory=list)

    @property
    def is_embedding(self) -> bool:
        if self.capabilities:
            return "embedding" in self.capabilities and "completion" not in self.capabilities
        return any(h in self.name.lower() for h in _EMBED_HINTS)

    @property
    def is_vision(self) -> bool:
        if self.capabilities:
            return "vision" in self.capabilities
        return any(h in self.name.lower() for h in _VISION_HINTS)

    @property
    def can_think(self) -> bool:
        return "thinking" in self.capabilities

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size": self.size,
            "family": self.family,
            "parameter_size": self.parameter_size,
            "quantization": self.quantization,
            "capabilities": self.capabilities,
            "is_embedding": self.is_embedding,
            "is_vision": self.is_vision,
        }


class ThinkStripper:
    """Removes <think>...</think> blocks from a token stream (Qwen3 / R1 style)."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self) -> None:
        self._buf = ""
        self._inside = False

    def feed(self, text: str) -> str:
        self._buf += text
        out: list[str] = []
        while self._buf:
            if self._inside:
                end = self._buf.find(self.CLOSE)
                if end == -1:
                    # keep a tail that might be the start of the closing tag
                    self._buf = self._buf[-(len(self.CLOSE) - 1):]
                    break
                self._buf = self._buf[end + len(self.CLOSE):].lstrip("\n")
                self._inside = False
            else:
                start = self._buf.find(self.OPEN)
                if start == -1:
                    # emit everything except a possible partial "<think" at the end
                    keep = 0
                    for i in range(1, len(self.OPEN)):
                        if self._buf.endswith(self.OPEN[:i]):
                            keep = i
                    out.append(self._buf[: len(self._buf) - keep])
                    self._buf = self._buf[len(self._buf) - keep:]
                    break
                out.append(self._buf[:start])
                self._buf = self._buf[start + len(self.OPEN):]
                self._inside = True
        return "".join(out)

    def flush(self) -> str:
        rest = "" if self._inside else self._buf
        self._buf = ""
        return rest


class OllamaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_url).rstrip("/")
        self._caps: dict[str, ModelInfo] = {}
        self._models_cache: tuple[float, list[ModelInfo]] | None = None

    # ------------------------------------------------------------------ basics
    def _client(self, timeout: float | None = 10.0) -> httpx.AsyncClient:
        # trust_env=False: never route local Ollama traffic through a system proxy.
        return httpx.AsyncClient(base_url=self.base_url, timeout=timeout, trust_env=False)

    async def version(self) -> str | None:
        try:
            async with self._client(3.0) as c:
                r = await c.get("/api/version")
                r.raise_for_status()
                return r.json().get("version")
        except Exception:
            return None

    async def list_models(self, refresh: bool = False) -> list[ModelInfo]:
        now = time.monotonic()
        if not refresh and self._models_cache and now - self._models_cache[0] < 15:
            return self._models_cache[1]
        try:
            async with self._client(5.0) as c:
                r = await c.get("/api/tags")
                r.raise_for_status()
                raw = r.json().get("models", [])
        except httpx.HTTPError as exc:
            raise OllamaError(self._unreachable_message()) from exc

        models: list[ModelInfo] = []
        for m in raw:
            name = m.get("name") or m.get("model")
            details = m.get("details") or {}
            info = ModelInfo(
                name=name,
                size=m.get("size", 0),
                family=details.get("family", ""),
                parameter_size=details.get("parameter_size", ""),
                quantization=details.get("quantization_level", ""),
            )
            info.capabilities = await self._capabilities(name)
            models.append(info)
        self._models_cache = (now, models)
        return models

    async def _capabilities(self, name: str) -> list[str]:
        if name in self._caps:
            return self._caps[name].capabilities
        caps: list[str] = []
        try:
            async with self._client(5.0) as c:
                r = await c.post("/api/show", json={"model": name})
                if r.status_code == 200:
                    caps = r.json().get("capabilities") or []
        except httpx.HTTPError:
            pass
        self._caps[name] = ModelInfo(name=name, capabilities=caps)
        return caps

    async def running(self) -> list[dict[str, Any]]:
        try:
            async with self._client(3.0) as c:
                r = await c.get("/api/ps")
                r.raise_for_status()
                models = r.json().get("models", [])
        except httpx.HTTPError:
            return []
        out = []
        for m in models:
            size = m.get("size") or 0
            vram = m.get("size_vram") or 0
            out.append(
                {
                    "name": m.get("name"),
                    "size": size,
                    "size_vram": vram,
                    "gpu_percent": round(100 * vram / size) if size else 0,
                    "context_length": m.get("context_length"),
                    "expires_at": m.get("expires_at"),
                }
            )
        return out

    def _unreachable_message(self) -> str:
        return (
            f"Cannot reach Ollama at {self.base_url}. Start it (open the Ollama app or run "
            "`ollama serve`) and try again."
        )

    # --------------------------------------------------------- model selection
    async def resolve_chat_model(self, preferred: str | None = None) -> str:
        models = await self.list_models()
        chat = [m for m in models if not m.is_embedding]
        names = [m.name for m in chat]
        if preferred:
            if preferred in names:
                return preferred
            # allow "qwen2.5" to match "qwen2.5:latest"
            for n in names:
                if n.split(":")[0] == preferred or n == f"{preferred}:latest":
                    return n
            raise OllamaError(
                f"Model '{preferred}' is not installed in Ollama. Run `ollama pull {preferred}` "
                f"or pick one of: {', '.join(names) or 'none installed'}."
            )
        if not chat:
            raise OllamaError("No chat model is installed in Ollama. Run e.g. `ollama pull qwen2.5:3b`.")
        return self.pick_default([m for m in chat])

    @staticmethod
    def pick_default(chat_models: list[ModelInfo]) -> str:
        def score(m: ModelInfo) -> tuple[int, int]:
            n = m.name.lower()
            s = 0
            if n.startswith("qwen"):
                s += 10
            if "coder" in n or m.is_vision or "vl" in n.split(":")[0]:
                s -= 5
            if n.startswith("nexgraft-"):  # fine-tuned for one workspace, not a general default
                s -= 8
            return (s, -m.size)

        return sorted(chat_models, key=score, reverse=True)[0].name

    async def finetuned_model(self, agent_id: str) -> str | None:
        """The workspace's fine-tuned model (nexgraft-<id>, see docs/FINETUNING.md), if installed."""
        try:
            models = await self.list_models()
        except OllamaError:
            return None
        for m in models:
            if m.name in (f"nexgraft-{agent_id}", f"nexgraft-{agent_id}:latest"):
                return m.name
        return None

    async def model_info(self, name: str) -> ModelInfo:
        for m in await self.list_models():
            if m.name == name:
                return m
        return ModelInfo(name=name, capabilities=await self._capabilities(name))

    async def resolve_vision_model(self) -> str | None:
        try:
            models = await self.list_models()
        except OllamaError:
            return None
        names = {m.name for m in models}
        if settings.vision_model:
            return settings.vision_model if settings.vision_model in names else None
        for m in models:
            if m.is_vision and not m.is_embedding:
                return m.name
        return None

    async def has_model(self, name: str) -> bool:
        try:
            models = await self.list_models()
        except OllamaError:
            return False
        return any(m.name == name or m.name == f"{name}:latest" for m in models)

    # -------------------------------------------------------------------- chat
    def _options(self, overrides: dict[str, Any] | None) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "num_ctx": settings.num_ctx,
            "temperature": settings.temperature,
            "num_predict": settings.num_predict,
        }
        if overrides:
            opts.update({k: v for k, v in overrides.items() if v is not None})
        return opts

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        options: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields {"type": "token", "content": str} and finally {"type": "stats", ...}."""
        info = await self.model_info(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": self._options(options),
            "keep_alive": settings.keep_alive,
        }
        if info.can_think:
            payload["think"] = False  # keep small models fast; answers stay focused
        stripper = ThinkStripper()
        started = time.perf_counter()
        try:
            async with self._client(timeout=None) as c:
                async with c.stream("POST", "/api/chat", json=payload) as r:
                    if r.status_code != 200:
                        body = (await r.aread()).decode("utf-8", "replace")
                        raise OllamaError(self._error_text(body, model))
                    async for line in r.aiter_lines():
                        if not line.strip():
                            continue
                        chunk = json.loads(line)
                        if chunk.get("error"):
                            raise OllamaError(str(chunk["error"]))
                        text = (chunk.get("message") or {}).get("content") or ""
                        if text:
                            visible = stripper.feed(text)
                            if visible:
                                yield {"type": "token", "content": visible}
                        if chunk.get("done"):
                            tail = stripper.flush()
                            if tail:
                                yield {"type": "token", "content": tail}
                            yield {"type": "stats", **self._stats(chunk, model, started)}
        except httpx.ConnectError as exc:
            raise OllamaError(self._unreachable_message()) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama stream interrupted ({exc.__class__.__name__})") from exc

    async def chat_json(
        self,
        model: str,
        messages: list[dict[str, Any]],
        schema: dict[str, Any],
        options: dict[str, Any] | None = None,
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Structured output constrained by a JSON schema."""
        info = await self.model_info(model)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "options": self._options({"temperature": 0, "num_predict": 600, **(options or {})}),
            "keep_alive": settings.keep_alive,
        }
        if info.can_think:
            payload["think"] = False
        try:
            async with self._client(timeout=timeout) as c:
                r = await c.post("/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise OllamaError(self._unreachable_message()) from exc
        except httpx.TimeoutException as exc:
            raise OllamaError(f"the model took longer than {timeout:.0f} s") from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama request failed ({exc.__class__.__name__})") from exc
        if r.status_code != 200:
            raise OllamaError(self._error_text(r.text, model))
        content = (r.json().get("message") or {}).get("content") or ""
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            match = re.search(r"\{.*\}", content, flags=re.S)
            if match:
                return json.loads(match.group(0))
            raise OllamaError("The model returned invalid JSON for the analysis step.") from exc

    async def describe_image(self, model: str, image_b64: str, prompt: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 600},
            "keep_alive": "2m",  # free VRAM soon; the chat model needs it
        }
        try:
            async with self._client(timeout=300.0) as c:
                r = await c.post("/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise OllamaError(self._unreachable_message()) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Vision request failed ({exc.__class__.__name__})") from exc
        if r.status_code != 200:
            raise OllamaError(self._error_text(r.text, model))
        return ((r.json().get("message") or {}).get("content") or "").strip()

    # --------------------------------------------------------------- embedding
    async def embed(self, model: str, inputs: list[str]) -> list[list[float]]:
        try:
            async with self._client(timeout=300.0) as c:
                r = await c.post("/api/embed", json={"model": model, "input": inputs, "keep_alive": settings.keep_alive})
        except httpx.ConnectError as exc:
            raise OllamaError(self._unreachable_message()) from exc
        except httpx.HTTPError as exc:
            raise OllamaError(f"Embedding request failed ({exc.__class__.__name__})") from exc
        if r.status_code != 200:
            raise OllamaError(self._error_text(r.text, model))
        return r.json().get("embeddings") or []

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _stats(chunk: dict[str, Any], model: str, started: float) -> dict[str, Any]:
        eval_count = chunk.get("eval_count") or 0
        eval_ns = chunk.get("eval_duration") or 0
        return {
            "model": model,
            "eval_count": eval_count,
            "prompt_eval_count": chunk.get("prompt_eval_count") or 0,
            "tokens_per_second": round(eval_count / (eval_ns / 1e9), 1) if eval_ns else None,
            "load_ms": round((chunk.get("load_duration") or 0) / 1e6),
            "wall_ms": round((time.perf_counter() - started) * 1000),
            "done_reason": chunk.get("done_reason"),
        }

    @staticmethod
    def _error_text(body: str, model: str) -> str:
        try:
            msg = json.loads(body).get("error", body)
        except (json.JSONDecodeError, AttributeError):
            msg = body
        if "not found" in str(msg).lower():
            return f"Model '{model}' is not installed. Run `ollama pull {model}`."
        return f"Ollama error: {msg}"


ollama = OllamaClient()
