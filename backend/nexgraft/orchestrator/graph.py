"""LangGraph orchestration graphs.

Analysis graph:   understand_input → analyze_problem → decompose_tasks → route_agents
Execution graph:  start → run_task (loops once per task) → synthesize (multi-task only)

Nodes stream progress to the web UI through LangGraph's custom stream writer.
Tasks run sequentially on purpose: on a 4 GB GPU, Ollama serves one request
at a time, so parallel agents would only compete for VRAM.
"""

from __future__ import annotations

import operator
import time
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter

from ..agents.base import Preparation, TaskContext
from ..agents.registry import registry
from ..config import settings
from ..llm.ollama import OllamaError, ollama
from ..multimodal.language import LANGUAGES, resolve_language
from ..tools.sequence import find_sequences_in_text
from .analyzer import analyze
from .context import build_synthesis_messages, build_task_messages


# ----------------------------------------------------------------- analysis
class AnalysisState(TypedDict, total=False):
    message: str
    attachments: list[dict[str, Any]]
    options: dict[str, Any]
    language_code: str
    language_auto: bool
    signals: dict[str, Any]
    model: str | None
    model_error: str | None
    plan: dict[str, Any]


def _stage(writer: StreamWriter, stage: str, status: str, label: str, detail: str = "") -> None:
    writer({"type": "stage", "stage": stage, "status": status, "label": label, "detail": detail})


async def understand_input(state: AnalysisState, writer: StreamWriter) -> dict[str, Any]:
    _stage(writer, "understand", "active", "Understanding input")
    message = state["message"]
    attachments = state.get("attachments") or []
    options = state.get("options") or {}
    lang, auto = resolve_language(options.get("language"), message)
    docs = [a for a in attachments if a.get("kind") == "document"]
    images = [a for a in attachments if a.get("kind") == "image"]
    sequences = find_sequences_in_text(message)
    signals = {
        "words": len(message.split()),
        "documents": len(docs),
        "images": len(images),
        "sequence_detected": bool(sequences),
        "input_modes": ["text"] + (["voice"] if options.get("voice") else []) + (["document"] if docs else []) + (["image"] if images else []),
    }
    model, model_error = None, None
    try:
        model = await ollama.resolve_chat_model(options.get("model") or settings.model or None)
    except OllamaError as exc:
        model_error = str(exc)
    detail = [f"Language: {lang.name}{' (auto-detected)' if auto else ''}"]
    if docs:
        detail.append(f"{len(docs)} document(s)")
    if images:
        detail.append(f"{len(images)} image(s)")
    if sequences:
        detail.append("biological sequence detected")
    _stage(writer, "understand", "done", "Understanding input", " · ".join(detail))
    return {"language_code": lang.code, "language_auto": auto, "signals": signals, "model": model, "model_error": model_error}


async def analyze_problem(state: AnalysisState, writer: StreamWriter) -> dict[str, Any]:
    options = state.get("options") or {}
    mode = options.get("router") or settings.router_mode
    model = state.get("model")
    label = "Problem & intent analysis"
    _stage(writer, "analyze", "active", label, f"LLM analyzer ({model})" if model and mode != "heuristic" else "Keyword router")
    attachments = state.get("attachments") or []
    note_parts, extra = [], []
    for a in attachments:
        if a.get("kind") == "image":
            note_parts.append(f"image '{a.get('name')}' showing: {(a.get('text') or '')[:300]}")
        else:
            note_parts.append(f"document '{a.get('name')}'")
            extra.append((a.get("text") or "")[:2000])
    plan = await analyze(
        state["message"],
        registry,
        ollama,
        model,
        mode,
        state.get("language_code", "en"),
        context_note="; ".join(note_parts),
        extra_text="\n".join(extra),
    )
    if state.get("model_error"):
        plan["router_notes"].insert(0, state["model_error"])
    how = {"llm": "LLM analyzer", "llm+guard": "LLM analyzer + keyword guard", "heuristic": "Keyword router"}[plan["router"]]
    _stage(writer, "analyze", "done", label, f"{how} · {plan['analysis_ms'] / 1000:.1f} s")
    return {"plan": plan}


async def decompose_tasks(state: AnalysisState, writer: StreamWriter) -> dict[str, Any]:
    plan = dict(state["plan"])
    tasks = []
    for i, t in enumerate(plan["tasks"], 1):
        tasks.append({**t, "id": f"t{i}"})
    plan["tasks"] = tasks
    plan["complexity"] = "multi" if len(tasks) > 1 else "single"
    detail = f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}" + (" (dynamic task graph)" if len(tasks) > 1 else "")
    _stage(writer, "decompose", "done", "Task decomposition", detail)
    return {"plan": plan}


async def route_agents(state: AnalysisState, writer: StreamWriter) -> dict[str, Any]:
    plan = dict(state["plan"])
    hw = plan.get("hardware_domain")
    for t in plan["tasks"]:
        spec = registry.agents[t["agent"]]
        t["agent_name"] = spec.name
        t["color"] = spec.color
        t["plugin"] = hw if spec.uses_plugins and hw in registry.plugins else None
        t["plugin_name"] = registry.plugins[t["plugin"]].name if t["plugin"] else None
    lang = LANGUAGES[state.get("language_code", "en")]
    plan["language"] = {"code": lang.code, "name": lang.name, "native": lang.native, "auto": state.get("language_auto", True)}
    plan["signals"] = state.get("signals", {})
    plan["model"] = state.get("model")
    names = " + ".join(t["agent_name"] for t in plan["tasks"])
    _stage(writer, "route", "done", "Intelligent routing", names)
    writer({"type": "analysis", "analysis": plan})
    return {"plan": plan}


def build_analysis_graph():
    g = StateGraph(AnalysisState)
    g.add_node("understand_input", understand_input)
    g.add_node("analyze_problem", analyze_problem)
    g.add_node("decompose_tasks", decompose_tasks)
    g.add_node("route_agents", route_agents)
    g.add_edge(START, "understand_input")
    g.add_edge("understand_input", "analyze_problem")
    g.add_edge("analyze_problem", "decompose_tasks")
    g.add_edge("decompose_tasks", "route_agents")
    g.add_edge("route_agents", END)
    return g.compile()


# ---------------------------------------------------------------- execution
class RunState(TypedDict, total=False):
    message: str
    history: list[dict[str, Any]]
    attachments: list[dict[str, Any]]
    options: dict[str, Any]
    tasks: list[dict[str, Any]]
    language_code: str
    index: int
    abort: bool
    results: Annotated[list[dict[str, Any]], operator.add]


def _public_source(s: dict[str, Any], n: int) -> dict[str, Any]:
    out = {k: v for k, v in s.items() if not k.startswith("_")}
    out["n"] = n
    return out


async def _resolve_model(agent_id: str, options: dict[str, Any]) -> str:
    per_agent = (options.get("agent_models") or {}).get(agent_id) or settings.agent_model_override(agent_id)
    if per_agent:
        return await ollama.resolve_chat_model(per_agent)
    return await ollama.resolve_chat_model(options.get("model") or settings.model or None)


async def start_run(state: RunState, writer: StreamWriter) -> dict[str, Any]:
    lang, _ = resolve_language((state.get("options") or {}).get("language"), state["message"])
    writer({"type": "run_start", "tasks": [{"id": t["id"], "agent": t["agent"], "title": t["title"]} for t in state["tasks"]]})
    return {"index": 0, "language_code": lang.code}


async def run_task(state: RunState, writer: StreamWriter) -> dict[str, Any]:
    idx = state["index"]
    task = state["tasks"][idx]
    options = state.get("options") or {}
    spec = registry.agents[task["agent"]]
    plugin = registry.plugins.get(task.get("plugin") or "")
    tid = task["id"]
    started = time.perf_counter()
    writer({"type": "task_start", "task_id": tid, "agent": spec.id, "title": task["title"], "plugin": plugin.id if plugin else None})

    ctx = TaskContext(
        message=state["message"],
        instruction=task.get("instruction") or state["message"],
        search_query=task.get("search_query", ""),
        agent_id=spec.id,
        plugin_id=plugin.id if plugin else None,
        attachments=state.get("attachments") or [],
        options=options,
        multi_task=len(state["tasks"]) > 1,
    )
    writer({"type": "task_phase", "task_id": tid, "phase": "grounding"})
    prep = await spec.prepare(ctx) if spec.prepare else Preparation()
    for call in prep.tool_calls:
        writer({"type": "tool", "task_id": tid, **call})
    sources = [_public_source(s, i) for i, s in enumerate(prep.sources, 1)]
    if sources:
        writer({"type": "sources", "task_id": tid, "sources": sources})
    for note in prep.notes:
        writer({"type": "note", "task_id": tid, "message": note})

    content = ""
    stats: dict[str, Any] = {}
    try:
        model = await _resolve_model(spec.id, options)
        writer({"type": "task_phase", "task_id": tid, "phase": "generating", "model": model})
        num_ctx = int(options.get("num_ctx") or settings.num_ctx)
        num_predict = int(options.get("num_predict") or settings.num_predict)
        messages = build_task_messages(
            spec=spec,
            plugin=plugin,
            task=task,
            all_tasks=state["tasks"],
            message=state["message"],
            history=state.get("history") or [],
            attachments=state.get("attachments") or [],
            prep=prep,
            language=LANGUAGES[state.get("language_code", "en")],
            num_ctx=num_ctx,
            num_predict=num_predict,
        )
        temperature = options.get("temperature")
        if temperature is None:
            temperature = spec.temperature if spec.temperature is not None else settings.temperature
        async for event in ollama.chat_stream(
            model, messages, {"temperature": temperature, "num_ctx": num_ctx, "num_predict": num_predict}
        ):
            if event["type"] == "token":
                content += event["content"]
                writer({"type": "token", "task_id": tid, "content": event["content"]})
            else:
                stats = {k: v for k, v in event.items() if k != "type"}
    except OllamaError as exc:
        writer({"type": "task_error", "task_id": tid, "message": str(exc)})
        return {
            "index": idx + 1,
            "abort": "Cannot reach Ollama" in str(exc),
            "results": [{"task_id": tid, "agent": spec.id, "agent_name": spec.name, "title": task["title"], "content": content, "error": str(exc)}],
        }

    stats["seconds"] = round(time.perf_counter() - started, 1)
    writer({"type": "task_end", "task_id": tid, "stats": stats})
    return {
        "index": idx + 1,
        "results": [{"task_id": tid, "agent": spec.id, "agent_name": spec.name, "title": task["title"], "content": content, "stats": stats}],
    }


def after_task(state: RunState) -> str:
    if state.get("abort"):
        return END
    if state["index"] < len(state["tasks"]):
        return "run_task"
    options = state.get("options") or {}
    wants = options.get("synthesis", settings.synthesis)
    ok = [r for r in state.get("results", []) if not r.get("error") and r.get("content")]
    return "synthesize" if wants and len(ok) > 1 else END


async def synthesize(state: RunState, writer: StreamWriter) -> dict[str, Any]:
    options = state.get("options") or {}
    results = [r for r in state.get("results", []) if not r.get("error")]
    writer({"type": "task_start", "task_id": "synthesis", "agent": "orchestrator", "title": "Unified output"})
    stats: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        model = await ollama.resolve_chat_model(options.get("model") or settings.model or None)
        num_ctx = int(options.get("num_ctx") or settings.num_ctx)
        messages = build_synthesis_messages(state["message"], results, LANGUAGES[state.get("language_code", "en")], num_ctx)
        async for event in ollama.chat_stream(model, messages, {"temperature": 0.3, "num_ctx": num_ctx, "num_predict": 500}):
            if event["type"] == "token":
                writer({"type": "token", "task_id": "synthesis", "content": event["content"]})
            else:
                stats = {k: v for k, v in event.items() if k != "type"}
    except OllamaError as exc:
        writer({"type": "task_error", "task_id": "synthesis", "message": str(exc)})
        return {}
    stats["seconds"] = round(time.perf_counter() - started, 1)
    writer({"type": "task_end", "task_id": "synthesis", "stats": stats})
    return {}


def build_run_graph():
    g = StateGraph(RunState)
    g.add_node("start", start_run)
    g.add_node("run_task", run_task)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "start")
    g.add_conditional_edges("start", lambda s: "run_task" if s.get("tasks") else END, ["run_task", END])
    g.add_conditional_edges("run_task", after_task, ["run_task", "synthesize", END])
    g.add_edge("synthesize", END)
    return g.compile()


analysis_graph = build_analysis_graph()
run_graph = build_run_graph()


def graph_structure() -> dict[str, Any]:
    """Nodes and edges of the compiled graphs, for the System page."""
    out = {}
    for name, graph in (("analysis", analysis_graph), ("execution", run_graph)):
        g = graph.get_graph()
        out[name] = {
            "nodes": [n for n in g.nodes],
            "edges": [{"source": e.source, "target": e.target, "conditional": e.conditional} for e in g.edges],
            "mermaid": g.draw_mermaid(),
        }
    return out
