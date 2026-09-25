from __future__ import annotations

import json
import os
import shutil
import urllib.request
from pathlib import Path
from typing import Any

from .recipes import RECIPES, Recipe

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(os.environ.get("NEXGRAFT_FINETUNE_DIR", ROOT / "finetune" / "work"))


def recipe(workspace: str) -> Recipe:
    if workspace not in RECIPES:
        raise SystemExit(f"Unknown workspace '{workspace}'. Choose from: {', '.join(RECIPES)}")
    return RECIPES[workspace]


def work_dir(workspace: str) -> Path:
    d = WORK / workspace
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def banner(text: str) -> None:
    print(f"\n=== {text}", flush=True)


# ------------------------------------------------------------------ Ollama
def _ollama_url() -> str:
    raw = (os.environ.get("OLLAMA_HOST") or "127.0.0.1:11434").strip().rstrip("/")
    scheme, _, rest = raw.rpartition("://")
    host, _, port = rest.partition(":")
    if host in ("", "0.0.0.0", "::", "[::]"):
        host = "127.0.0.1"
    return f"{scheme or 'http'}://{host}:{port or '11434'}"


# Local traffic must never go through a system proxy.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def ollama_api(path: str, payload: dict[str, Any] | None = None, timeout: float = 600) -> dict[str, Any]:
    data = None if payload is None else json.dumps({"stream": False, **payload}).encode()
    req = urllib.request.Request(_ollama_url() + path, data=data, headers={"Content-Type": "application/json"})
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "{}")


def ollama_models() -> list[str]:
    try:
        return [m["name"] for m in ollama_api("/api/tags", timeout=5).get("models", [])]
    except OSError:
        return []


def ollama_has(name: str, models: list[str] | None = None) -> str | None:
    """Returns the installed tag for `name` (accepting an implicit ':latest'), or None."""
    for m in models if models is not None else ollama_models():
        if m == name or m == f"{name}:latest":
            return m
    return None


def ollama_unload_all() -> None:
    """Frees the GPU before training: Ollama keeps models loaded for a while after each request."""
    try:
        running = ollama_api("/api/ps", timeout=5).get("models", [])
    except OSError:
        return
    for m in running:
        try:
            ollama_api("/api/generate", {"model": m["name"], "keep_alive": 0}, timeout=30)
            print(f"Unloaded {m['name']} from Ollama to free GPU memory.")
        except OSError:
            pass


def ollama_cli() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return str(local) if local.is_file() else None
