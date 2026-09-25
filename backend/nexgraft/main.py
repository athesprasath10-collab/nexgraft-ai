"""NEXGRAFT AI — FastAPI application (local prototype)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Literal
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import __version__
from .agents.registry import registry
from .config import FRONTEND_DIST, ROOT_DIR, settings
from .knowledge.store import knowledge_base
from .llm.ollama import OllamaError, ollama
from .multimodal.documents import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, DocumentError, extract_text
from .multimodal.language import public_languages
from .multimodal.vision import VisionUnavailable, describe_image
from .orchestrator.graph import analysis_graph, graph_structure, run_graph
from .services.attachments import attachment_store, safe_filename
from .services.runner import run_python
from .tools import TOOL_REGISTRY, ToolInputError
from .tools.literature import keywords_from_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("nexgraft")

MAX_UPLOAD = 25 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(_index_knowledge())
    yield
    task.cancel()


async def _index_knowledge() -> None:
    try:
        await knowledge_base.build()
        stats = knowledge_base.stats()
        log.info("Knowledge base ready: %s collections, retrieval mode %s", len(stats["collections"]), stats["mode"])
    except Exception:  # never block the app on indexing
        log.exception("Knowledge indexing failed")


app = FastAPI(title="NEXGRAFT AI", version=__version__, lifespan=lifespan)

# --------------------------------------------------------------------- safety
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _allowed_hosts() -> set[str]:
    return LOCAL_HOSTS | set(settings.extra_allowed_hosts)


@app.middleware("http")
async def local_only(request: Request, call_next):
    """Blocks DNS-rebinding and cross-site requests to this local server."""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if request.headers.get("host", "").startswith("["):
        host = request.headers["host"].split("]")[0].strip("[")
    allowed = _allowed_hosts()
    if host not in allowed:
        return JSONResponse({"detail": f"Host '{host}' is not allowed. Add it to NEXGRAFT_ALLOWED_HOSTS."}, status_code=403)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and urlparse(origin).hostname not in allowed:
            return JSONResponse({"detail": "Cross-origin requests are not allowed."}, status_code=403)
    return await call_next(request)


# -------------------------------------------------------------------- models
class Options(BaseModel):
    model: str | None = None
    agent_models: dict[str, str] = Field(default_factory=dict)
    router: Literal["hybrid", "heuristic"] | None = None
    language: str | None = "auto"
    literature: bool | None = None
    literature_limit: int | None = Field(default=None, ge=1, le=10)
    synthesis: bool | None = None
    use_knowledge: bool | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    num_ctx: int | None = Field(default=None, ge=1024, le=131072)
    num_predict: int | None = Field(default=None, ge=64, le=8192)
    voice: bool = False

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)


class AnalyzeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    attachments: list[str] = Field(default_factory=list)
    options: Options = Field(default_factory=Options)


class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=40000)


class TaskIn(BaseModel):
    id: str = Field(max_length=20)
    agent: str
    title: str = Field(max_length=120)
    instruction: str = Field(max_length=20000)
    search_query: str = Field(default="", max_length=300)
    plugin: str | None = None


class RunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    history: list[HistoryItem] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    tasks: list[TaskIn] | None = None
    agent: str | None = None
    plugin: str | None = None
    options: Options = Field(default_factory=Options)


class ToolRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)


class ExecuteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200_000)
    attachments: list[str] = Field(default_factory=list)


class CollectionRequest(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,39}$")


# ---------------------------------------------------------------- streaming
def _ndjson(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, default=str) + "\n"


def _stream(graph, state: dict[str, Any]) -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        started = time.perf_counter()
        try:
            async for chunk in graph.astream(state, stream_mode="custom", config={"recursion_limit": 40}):
                yield _ndjson(chunk)
        except OllamaError as exc:
            yield _ndjson({"type": "error", "message": str(exc)})
        except Exception as exc:  # surface unexpected errors to the UI
            log.exception("Graph execution failed")
            yield _ndjson({"type": "error", "message": f"{exc.__class__.__name__}: {exc}"})
        yield _ndjson({"type": "done", "seconds": round(time.perf_counter() - started, 1)})

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- endpoints
@app.get("/api/health")
async def health() -> dict[str, Any]:
    version = await ollama.version()
    return {"ok": True, "app_version": __version__, "ollama": {"reachable": version is not None, "version": version, "url": ollama.base_url}}


def _spline_scene() -> str | None:
    if settings.spline_scene_url:
        return settings.spline_scene_url
    for folder in (FRONTEND_DIST, ROOT_DIR / "frontend" / "public"):
        if (folder / "spline" / "scene.splinecode").is_file():
            return "/spline/scene.splinecode"
    return None


def _hero_model() -> str | None:
    if settings.hero_model_url:
        return settings.hero_model_url
    for folder in (FRONTEND_DIST, ROOT_DIR / "frontend" / "public"):
        if (folder / "models" / "hero.glb").is_file():
            return "/models/hero.glb"
    return None


@app.get("/api/config")
async def config() -> dict[str, Any]:
    return {
        "app_version": __version__,
        "agents": [a.public() for a in registry.agents.values()],
        "plugins": [p.public() for p in registry.plugins.values()],
        "tools": [t.public() for t in TOOL_REGISTRY.values()],
        "languages": public_languages(),
        "defaults": {
            "model": settings.model or None,
            "router": settings.router_mode,
            "synthesis": settings.synthesis,
            "literature": settings.literature_search,
            "num_ctx": settings.num_ctx,
            "num_predict": settings.num_predict,
            "temperature": settings.temperature,
        },
        "features": {
            "code_runner": settings.code_runner,
            "code_timeout": settings.code_timeout,
            "literature": settings.literature_search,
            "document_types": sorted(DOCUMENT_EXTENSIONS),
            "image_types": sorted(IMAGE_EXTENSIONS),
        },
        "spline_scene": _spline_scene(),
        "hero_model": _hero_model(),
    }


@app.get("/api/status")
async def status() -> dict[str, Any]:
    version = await ollama.version()
    out: dict[str, Any] = {
        "ollama": {"reachable": version is not None, "version": version, "url": ollama.base_url},
        "models": [],
        "running": [],
        "default_model": None,
        "vision_model": None,
        "embed_model": {"name": settings.embed_model, "installed": False},
        "knowledge": knowledge_base.stats(),
        "settings": {
            "num_ctx": settings.num_ctx,
            "num_predict": settings.num_predict,
            "router": settings.router_mode,
            "keep_alive": settings.keep_alive,
            "agent_models": {a: settings.agent_model_override(a) for a in registry.agents if settings.agent_model_override(a)},
        },
    }
    if version is None:
        return out
    try:
        models = await ollama.list_models(refresh=True)
        out["models"] = [m.as_dict() for m in models]
        out["default_model"] = await ollama.resolve_chat_model(settings.model or None)
    except OllamaError as exc:
        out["model_error"] = str(exc)
    out["running"] = await ollama.running()
    out["vision_model"] = await ollama.resolve_vision_model()
    out["embed_model"]["installed"] = await ollama.has_model(settings.embed_model)
    return out


@app.get("/api/graph")
async def graph() -> dict[str, Any]:
    return graph_structure()


@app.post("/api/analyze")
async def analyze_endpoint(req: AnalyzeRequest) -> StreamingResponse:
    state = {
        "message": req.message.strip(),
        "attachments": attachment_store.resolve(req.attachments),
        "options": req.options.as_dict(),
    }
    return _stream(analysis_graph, state)


def _validate_tasks(req: RunRequest) -> list[dict[str, Any]]:
    if req.tasks:
        tasks = []
        for i, t in enumerate(req.tasks[:4], 1):
            if t.agent not in registry.agents:
                raise HTTPException(400, f"Unknown workspace '{t.agent}'.")
            plugin = t.plugin if t.plugin in registry.plugins and registry.plugins[t.plugin].agent == t.agent else None
            tasks.append({**t.model_dump(), "id": f"t{i}", "plugin": plugin})
        return tasks
    agent = req.agent or "general"
    if agent not in registry.agents:
        raise HTTPException(400, f"Unknown workspace '{agent}'.")
    spec = registry.agents[agent]
    plugin = req.plugin if req.plugin in registry.plugins and registry.plugins[req.plugin].agent == agent else None
    return [{
        "id": "t1",
        "agent": agent,
        "title": spec.short_name + (f" · {registry.plugins[plugin].name}" if plugin else ""),
        "instruction": req.message.strip(),
        "search_query": keywords_from_text(req.message),
        "plugin": plugin,
    }]


@app.post("/api/run")
async def run_endpoint(req: RunRequest) -> StreamingResponse:
    state = {
        "message": req.message.strip(),
        "history": [h.model_dump() for h in req.history[-10:]],
        "attachments": attachment_store.resolve(req.attachments),
        "options": req.options.as_dict(),
        "tasks": _validate_tasks(req),
        "results": [],
    }
    return _stream(run_graph, state)


@app.post("/api/attachments")
async def upload_attachment(file: UploadFile = File(...), hint: str = Form("")) -> dict[str, Any]:
    name = file.filename or "upload"
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 25 MB.")
    ext = Path(name).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        try:
            model, description = await describe_image(ollama, data, hint[:500])
        except VisionUnavailable as exc:
            raise HTTPException(422, str(exc)) from exc
        return attachment_store.save(kind="image", name=name, data=data, text=description, meta={"model": model})
    if ext in DOCUMENT_EXTENSIONS or not ext:
        try:
            text = extract_text(data, name)
        except DocumentError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not text.strip():
            raise HTTPException(422, "No text could be extracted from this file.")
        return attachment_store.save(kind="document", name=name, data=data, text=text)
    raise HTTPException(415, f"Unsupported file type '{ext}'.")


@app.get("/api/tools")
async def list_tools(agent: str | None = None, plugin: str | None = None) -> list[dict[str, Any]]:
    tools = TOOL_REGISTRY.values()
    if agent:
        allowed = set(registry.tools_for(agent, plugin)) if agent in registry.agents else set()
        tools = [t for t in tools if t.id in allowed]
    return [t.public() for t in tools]


@app.post("/api/tools/{tool_id}")
async def run_tool(tool_id: str, req: ToolRequest) -> dict[str, Any]:
    tool = TOOL_REGISTRY.get(tool_id)
    if not tool:
        raise HTTPException(404, "Unknown tool.")
    started = time.perf_counter()
    try:
        output = await tool.execute(req.params)
    except ToolInputError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"tool": tool.id, "name": tool.name, "output": output, "ms": round((time.perf_counter() - started) * 1000)}


@app.post("/api/execute")
async def execute(req: ExecuteRequest) -> dict[str, Any]:
    if not settings.code_runner:
        raise HTTPException(403, "The local code runner is disabled (NEXGRAFT_CODE_RUNNER=false).")
    files = []
    for att_id in req.attachments[:10]:
        original = attachment_store.original(att_id)
        if original:
            files.append(original)
    return await run_python(req.code, files, settings.code_timeout)


# ---------------------------------------------------------------- knowledge
@app.get("/api/knowledge")
async def knowledge() -> dict[str, Any]:
    return knowledge_base.stats()


@app.post("/api/knowledge/reindex")
async def reindex(collection: str | None = None) -> dict[str, Any]:
    await knowledge_base.build(only=collection, force=True)
    return knowledge_base.stats()


@app.post("/api/knowledge/collections")
async def create_collection(req: CollectionRequest) -> dict[str, Any]:
    (settings.knowledge_dir / req.id).mkdir(parents=True, exist_ok=True)
    await knowledge_base.build(only=req.id)
    return knowledge_base.stats()


def _collection_dir(collection: str) -> Path:
    if collection not in knowledge_base.collection_ids():
        raise HTTPException(404, "Unknown collection.")
    return settings.knowledge_dir / collection


@app.post("/api/knowledge/{collection}/upload")
async def upload_knowledge(collection: str, file: UploadFile = File(...)) -> dict[str, Any]:
    folder = _collection_dir(collection)
    name = safe_filename(file.filename or "document.txt")
    if Path(name).suffix.lower() not in DOCUMENT_EXTENSIONS:
        raise HTTPException(415, "Upload a PDF, DOCX, Markdown or text-based document.")
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "File is larger than 25 MB.")
    try:
        extract_text(data, name)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc
    (folder / name).write_bytes(data)
    await knowledge_base.build(only=collection)
    return knowledge_base.stats()


@app.delete("/api/knowledge/{collection}/{filename}")
async def delete_knowledge(collection: str, filename: str) -> dict[str, Any]:
    folder = _collection_dir(collection)
    target = (folder / safe_filename(filename)).resolve()
    if target.parent != folder.resolve() or not target.is_file():
        raise HTTPException(404, "Document not found.")
    target.unlink()
    await knowledge_base.build(only=collection)
    return knowledge_base.stats()


# ------------------------------------------------------------------ frontend
_ASSET_RE = re.compile(r"^[\w\-./]+$")


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    if not FRONTEND_DIST.is_dir():
        return JSONResponse(
            {"detail": "Frontend not built. Run `npm install && npm run build` in ./frontend, or use the Vite dev server (npm run dev)."},
            status_code=503,
        )
    if path and _ASSET_RE.match(path) and ".." not in path:
        candidate = (FRONTEND_DIST / path).resolve()
        if candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
    return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})
