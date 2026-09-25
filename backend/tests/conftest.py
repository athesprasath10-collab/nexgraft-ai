import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexgraft.config import settings  # noqa: E402

settings.extra_allowed_hosts.append("testserver")


@pytest.fixture
def fake_ollama(monkeypatch):
    """Replaces the Ollama client with deterministic fakes (no model needed)."""
    from nexgraft.llm.ollama import ModelInfo, OllamaError, ollama

    calls = {"chat": [], "json": []}

    async def list_models(refresh=False):
        return [ModelInfo(name="qwen2.5:3b", capabilities=["completion"])]

    async def resolve_chat_model(preferred=None):
        if preferred and preferred != "qwen2.5:3b":
            raise OllamaError(f"Model '{preferred}' is not installed.")
        return "qwen2.5:3b"

    async def chat_json(model, messages, schema, options=None, timeout=120):
        calls["json"].append(messages[-1]["content"])
        return {
            "domain": "Physics",
            "intent": "Explain a concept",
            "capabilities": ["Explanation"],
            "hardware_domain": "none",
            "tasks": [{"workspace": "general", "title": "Explain", "instruction": "Explain it.", "search_query": "newton laws"}],
        }

    async def chat_stream(model, messages, options=None):
        calls["chat"].append(messages)
        for word in ["Hello", " from", " NEXGRAFT"]:
            yield {"type": "token", "content": word}
        yield {"type": "stats", "model": model, "eval_count": 3, "tokens_per_second": 30.0}

    async def has_model(name):
        return False

    async def version():
        return "0.0-test"

    async def resolve_vision_model():
        return None

    monkeypatch.setattr(ollama, "list_models", list_models)
    monkeypatch.setattr(ollama, "resolve_chat_model", resolve_chat_model)
    monkeypatch.setattr(ollama, "chat_json", chat_json)
    monkeypatch.setattr(ollama, "chat_stream", chat_stream)
    monkeypatch.setattr(ollama, "has_model", has_model)
    monkeypatch.setattr(ollama, "version", version)
    monkeypatch.setattr(ollama, "resolve_vision_model", resolve_vision_model)
    monkeypatch.setattr(settings, "literature_search", False)
    return calls
