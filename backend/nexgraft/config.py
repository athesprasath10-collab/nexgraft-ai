"""Runtime configuration for the NEXGRAFT local prototype.

Values come from environment variables, optionally loaded from a `.env` file
in the repository root (see `.env.example`). No third-party dotenv package is
needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"


def _load_dotenv(path: Path) -> None:
    """Minimal KEY=VALUE loader. Real environment variables win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(ROOT_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _ollama_url(raw: str) -> str:
    """Accepts OLLAMA_HOST values like '0.0.0.0', '127.0.0.1:11434' or 'http://host:port'."""
    raw = (raw or "127.0.0.1:11434").strip().rstrip("/")
    scheme, _, rest = raw.rpartition("://")
    scheme = scheme or "http"
    host, _, port = rest.partition(":")
    if host in ("", "0.0.0.0", "::", "[::]"):
        host = "127.0.0.1"  # a bind-all address is not a valid client target
    return f"{scheme}://{host}:{port or '11434'}"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    ollama_url: str = field(default_factory=lambda: _ollama_url(_env("OLLAMA_HOST")))
    # Empty = auto-select the first installed Qwen chat model.
    model: str = field(default_factory=lambda: _env("NEXGRAFT_MODEL"))
    embed_model: str = field(default_factory=lambda: _env("NEXGRAFT_EMBED_MODEL", "nomic-embed-text"))
    # Empty = auto-detect an installed model with the "vision" capability.
    vision_model: str = field(default_factory=lambda: _env("NEXGRAFT_VISION_MODEL"))

    num_ctx: int = field(default_factory=lambda: _env_int("NEXGRAFT_NUM_CTX", 8192))
    num_predict: int = field(default_factory=lambda: _env_int("NEXGRAFT_NUM_PREDICT", 1200))
    temperature: float = field(default_factory=lambda: _env_float("NEXGRAFT_TEMPERATURE", 0.4))
    keep_alive: str = field(default_factory=lambda: _env("NEXGRAFT_KEEP_ALIVE", "15m"))

    # "hybrid" = LLM analyzer with keyword fallback, "heuristic" = keyword router only.
    router_mode: str = field(default_factory=lambda: _env("NEXGRAFT_ROUTER", "hybrid"))
    # Seconds before the LLM analyzer gives up and the keyword router takes over.
    analyzer_timeout: float = field(default_factory=lambda: _env_float("NEXGRAFT_ANALYZER_TIMEOUT", 60))
    synthesis: bool = field(default_factory=lambda: _env_bool("NEXGRAFT_SYNTHESIS", True))

    host: str = field(default_factory=lambda: _env("NEXGRAFT_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("NEXGRAFT_PORT", 8000))
    # Extra hostnames allowed in the Host header (e.g. a LAN IP for a demo).
    extra_allowed_hosts: list[str] = field(
        default_factory=lambda: [h.strip() for h in _env("NEXGRAFT_ALLOWED_HOSTS").split(",") if h.strip()]
    )

    literature_search: bool = field(default_factory=lambda: _env_bool("NEXGRAFT_LITERATURE", True))
    code_runner: bool = field(default_factory=lambda: _env_bool("NEXGRAFT_CODE_RUNNER", True))
    code_timeout: int = field(default_factory=lambda: _env_int("NEXGRAFT_CODE_TIMEOUT", 60))

    spline_scene_url: str = field(default_factory=lambda: _env("NEXGRAFT_SPLINE_SCENE"))

    knowledge_dir: Path = field(default_factory=lambda: Path(_env("NEXGRAFT_KNOWLEDGE_DIR", str(ROOT_DIR / "knowledge"))))
    data_dir: Path = field(default_factory=lambda: Path(_env("NEXGRAFT_DATA_DIR", str(ROOT_DIR / "data"))))

    def agent_model_override(self, agent_id: str) -> str:
        """Optional per-workspace model, e.g. NEXGRAFT_MODEL_BIOINFORMATICS=qwen2.5-coder:3b."""
        return _env(f"NEXGRAFT_MODEL_{agent_id.upper()}")

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"


settings = Settings()
