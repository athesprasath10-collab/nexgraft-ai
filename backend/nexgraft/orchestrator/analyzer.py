"""Problem analysis: LLM analyzer with a deterministic keyword fallback and guard."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from ..agents.registry import Registry
from ..config import settings
from ..llm.ollama import OllamaClient, OllamaError
from ..tools.literature import keywords_from_text
from .heuristics import detect_plugin, domain_label, heuristic_analysis

log = logging.getLogger("nexgraft.analyzer")

MAX_TASKS = 4


def analyzer_schema(registry: Registry) -> dict[str, Any]:
    plugins = [p.id for p in registry.plugins_for("hardware")] + ["none"]
    return {
        "type": "object",
        "properties": {
            "domain": {"type": "string"},
            "intent": {"type": "string"},
            "capabilities": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "hardware_domain": {"type": "string", "enum": plugins},
            "tasks": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_TASKS,
                "items": {
                    "type": "object",
                    "properties": {
                        "workspace": {"type": "string", "enum": list(registry.agents)},
                        "title": {"type": "string"},
                        "instruction": {"type": "string"},
                        "search_query": {"type": "string"},
                    },
                    "required": ["workspace", "title", "instruction", "search_query"],
                },
            },
        },
        "required": ["domain", "intent", "capabilities", "hardware_domain", "tasks"],
    }


_EXAMPLES = [
    (
        "Explain Newton's laws.",
        {"domain": "Physics", "intent": "Understand Newton's laws of motion", "capabilities": ["Explanation"],
         "hardware_domain": "none",
         "tasks": [{"workspace": "general", "title": "Explain Newton's laws", "instruction": "Explain Newton's three laws of motion with examples.", "search_query": "Newton laws of motion"}]},
    ),
    (
        "Generate a Python workflow for protein sequence analysis.",
        {"domain": "Bioinformatics", "intent": "Get code for analysing protein sequences", "capabilities": ["Sequence analysis", "Python code"],
         "hardware_domain": "none",
         "tasks": [{"workspace": "bioinformatics", "title": "Protein sequence analysis workflow", "instruction": "Write a Python workflow for protein sequence analysis and explain it.", "search_query": "protein sequence analysis Python"}]},
    ),
    (
        "Explain recent research on diabetes biomarkers.",
        {"domain": "Medical Research", "intent": "Summarise recent research on diabetes biomarkers", "capabilities": ["Literature search", "Evidence synthesis"],
         "hardware_domain": "none",
         "tasks": [{"workspace": "medical", "title": "Diabetes biomarker research", "instruction": "Summarise recent research on diabetes biomarkers with sources.", "search_query": "diabetes biomarkers"}]},
    ),
    (
        "Design a wearable biomedical device and explain the medical research supporting the selected measurements.",
        {"domain": "Biomedical Engineering", "intent": "Design a wearable and justify its measurements with research", "capabilities": ["Hardware design", "Medical research"],
         "hardware_domain": "biomedical",
         "tasks": [
             {"workspace": "medical", "title": "Research behind the measurements", "instruction": "Summarise the medical research supporting which physiological measurements a wearable should take.", "search_query": "wearable physiological monitoring validation"},
             {"workspace": "hardware", "title": "Wearable hardware design", "instruction": "Recommend sensors, electronics and design considerations for the wearable.", "search_query": "wearable biomedical sensors"},
         ]},
    ),
]


def analyzer_messages(message: str, registry: Registry, context_note: str = "") -> list[dict[str, str]]:
    lines = []
    for spec in registry.agents.values():
        lines.append(f"- {spec.id}: {spec.description} Capabilities: {', '.join(spec.capabilities)}.")
    plugins = ", ".join(f"{p.id} ({p.name})" for p in registry.plugins_for("hardware"))
    system = (
        "You are the NEXGRAFT orchestration analyzer. Decide which specialist workspaces are needed for the user's "
        "request and write a task plan. Do NOT answer the request itself.\n\n"
        "Workspaces:\n" + "\n".join(lines) + "\n\n"
        f"Hardware domains: {plugins}, or none.\n\n"
        "Rules:\n"
        "1. Use the FEWEST workspaces needed. Most requests need exactly one.\n"
        "2. Use several workspaces only when the request clearly has separate parts needing different expertise.\n"
        "3. General explanations (e.g. physics, maths, history, writing, planning) use only 'general'.\n"
        "4. Bioinformatics = biological sequences/data and code for them. Medical = medical/health research and evidence "
        "(never diagnosis). Hardware = physical devices, sensors, circuits, materials, structures.\n"
        "5. Each task has one workspace (never repeat a workspace), a short title, an English instruction for that "
        "specialist, and an English keyword search_query (3–6 words).\n"
        "6. Write domain, intent and capabilities in English. Reply with JSON only."
    )
    shots: list[dict[str, str]] = [{"role": "system", "content": system}]
    for q, a in _EXAMPLES:
        shots.append({"role": "user", "content": q})
        shots.append({"role": "assistant", "content": json.dumps(a)})
    user = message if not context_note else f"{message}\n\n[Context: {context_note}]"
    shots.append({"role": "user", "content": user})
    return shots


def normalise_llm_plan(raw: dict[str, Any], message: str, registry: Registry) -> dict[str, Any] | None:
    tasks_by_agent: dict[str, dict[str, Any]] = {}
    for t in raw.get("tasks") or []:
        aid = str(t.get("workspace", "")).strip().lower()
        if aid not in registry.agents:
            continue
        instruction = str(t.get("instruction") or "").strip() or message
        if aid in tasks_by_agent:  # merge duplicate workspaces into one task
            tasks_by_agent[aid]["instruction"] += " " + instruction
            continue
        tasks_by_agent[aid] = {
            "agent": aid,
            "title": str(t.get("title") or registry.agents[aid].short_name).strip()[:80],
            "instruction": instruction,
            "search_query": str(t.get("search_query") or "").strip() or keywords_from_text(message),
        }
    if not tasks_by_agent:
        return None
    hw = str(raw.get("hardware_domain") or "none").lower()
    return {
        "domain": str(raw.get("domain") or "").strip()[:80],
        "intent": str(raw.get("intent") or "").strip()[:240],
        "capabilities": [str(c).strip() for c in (raw.get("capabilities") or []) if str(c).strip()][:5],
        "hardware_domain": hw if hw in registry.plugins else None,
        "tasks": list(tasks_by_agent.values())[:MAX_TASKS],
    }


def apply_guard(plan: dict[str, Any], heuristic: dict[str, Any], message: str, language: str) -> list[str]:
    """Correct obvious small-model misroutes using keyword evidence. Returns notes."""
    notes: list[str] = []
    scores = heuristic["scores"]
    llm_agents = [t["agent"] for t in plan["tasks"]]
    heur_agents = [t["agent"] for t in heuristic["tasks"]]
    if language != "en":
        return notes  # keyword lists are English; trust the multilingual model
    # 1. LLM said "general only" but there is strong specialist evidence.
    if llm_agents == ["general"] and heur_agents != ["general"]:
        best = max(heur_agents, key=lambda a: scores.get(a, 0))
        if scores.get(best, 0) >= 5:
            plan["tasks"] = heuristic["tasks"]
            notes.append(f"Keyword guard: strong {best} signals ({', '.join(heuristic['matched'].get(best, [])[:4])}), so the plan uses the keyword router.")
            return notes
    # 2. LLM activated extra specialists with zero keyword evidence in a short request.
    if len(llm_agents) > 1 and len(message.split()) <= 25:
        keep = [t for t in plan["tasks"] if t["agent"] == "general" or scores.get(t["agent"], 0) > 0]
        dropped = [t["agent"] for t in plan["tasks"] if t not in keep]
        if dropped and keep:
            plan["tasks"] = keep
            notes.append(f"Keyword guard: removed {', '.join(dropped)} (no supporting signals in a short request).")
    return notes


async def analyze(
    message: str,
    registry: Registry,
    client: OllamaClient,
    model: str | None,
    mode: str,
    language: str,
    context_note: str = "",
    extra_text: str = "",
) -> dict[str, Any]:
    started = time.perf_counter()
    heuristic = heuristic_analysis(message, registry, extra_text)
    router, notes, plan = "heuristic", [], None
    if mode != "heuristic" and model:
        try:
            raw = await client.chat_json(
                model, analyzer_messages(message, registry, context_note), analyzer_schema(registry), timeout=settings.analyzer_timeout
            )
            plan = normalise_llm_plan(raw, message, registry)
            if plan is None:
                notes.append("The model's plan named no valid workspace; used the keyword router instead.")
            else:
                router = "llm"
                guard_notes = apply_guard(plan, heuristic, message, language)
                if guard_notes:
                    router = "llm+guard"
                    notes.extend(guard_notes)
        except (OllamaError, ValueError, KeyError, TypeError) as exc:
            log.warning("LLM analysis failed: %s", exc)
            notes.append(f"LLM analysis unavailable ({exc}); used the keyword router.")
            plan = None
    if plan is None:
        plan = {k: heuristic[k] for k in ("domain", "intent", "capabilities", "hardware_domain", "tasks")}
        router = "heuristic"

    agents = [t["agent"] for t in plan["tasks"]]
    if "hardware" in agents and not plan.get("hardware_domain"):
        plan["hardware_domain"] = heuristic.get("hardware_domain") or detect_plugin(f"{message}\n{extra_text}", registry)
    if not plan.get("domain"):
        plan["domain"] = domain_label(agents, plan.get("hardware_domain"), registry)
    if not plan.get("capabilities"):
        plan["capabilities"] = [c for a in agents for c in registry.agents[a].capabilities[:2]][:5]
    if not plan.get("intent"):
        plan["intent"] = heuristic["intent"]

    plan.update(
        router=router,
        router_notes=notes,
        keyword_scores=heuristic["scores"],
        analysis_ms=round((time.perf_counter() - started) * 1000),
        analyzer_model=model if router.startswith("llm") else None,
    )
    return plan
