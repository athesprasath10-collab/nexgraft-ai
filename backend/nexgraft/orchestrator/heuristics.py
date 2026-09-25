"""Deterministic keyword router.

Used when the router is set to "heuristic" (fastest), as the fallback when the
LLM analyzer fails, and as a guard that catches obvious small-model misroutes.
Keywords are declared on each AgentSpec / PluginSpec, so new workspaces bring
their own routing vocabulary.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from ..agents.registry import Registry
from ..tools.literature import keywords_from_text
from ..tools.sequence import find_sequences_in_text

SPECIALIST_MIN_SCORE = 2.5
RELATIVE_THRESHOLD = 0.4
_PLANNING_RE = re.compile(
    r"\b(plan|planning|project|roadmap|develop|build|create a system|startup|prototype|end[- ]to[- ]end|overall)\b", re.I
)


@lru_cache(maxsize=2048)
def _pattern(keyword: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])")


def keyword_score(text: str, keywords: dict[str, float]) -> tuple[float, list[str]]:
    lower = text.lower()
    score, hits = 0.0, []
    for kw, weight in keywords.items():
        if _pattern(kw).search(lower):
            score += weight
            hits.append(kw)
    return score, hits


def score_agents(text: str, registry: Registry) -> dict[str, dict[str, Any]]:
    scores: dict[str, dict[str, Any]] = {}
    for aid, spec in registry.agents.items():
        s, hits = keyword_score(text, spec.keywords)
        scores[aid] = {"score": s, "hits": hits}
    if "bioinformatics" in scores and find_sequences_in_text(text):
        scores["bioinformatics"]["score"] += 6.0
        scores["bioinformatics"]["hits"].append("<sequence detected>")
    return scores


def detect_plugin(text: str, registry: Registry, agent_id: str = "hardware") -> str | None:
    best, best_score = None, 0.0
    for plugin in registry.plugins_for(agent_id):
        s, _ = keyword_score(text, plugin.keywords)
        if s > best_score:
            best, best_score = plugin.id, s
    return best


def domain_label(agent_ids: list[str], plugin_id: str | None, registry: Registry) -> str:
    specialists = [a for a in agent_ids if a != "general"] or agent_ids
    labels = []
    for a in specialists:
        if a == "hardware" and plugin_id and plugin_id in registry.plugins:
            labels.append(registry.plugins[plugin_id].name)
        elif a == "general":
            labels.append("General")
        else:
            labels.append(registry.agents[a].short_name)
    # "Biomedical Engineering" already covers medical + hardware for a biomedical device
    if "Biomedical Engineering" in labels and "Medical Research" in labels:
        labels.remove("Medical Research")
    return " + ".join(dict.fromkeys(labels))


def heuristic_analysis(message: str, registry: Registry, extra_text: str = "") -> dict[str, Any]:
    text = f"{message}\n{extra_text}".strip()
    scores = score_agents(text, registry)
    specialists = [a for a in registry.agents if a != "general"]
    top = max((scores[a]["score"] for a in specialists), default=0.0)
    selected = [
        a for a in specialists
        if scores[a]["score"] >= SPECIALIST_MIN_SCORE and scores[a]["score"] >= RELATIVE_THRESHOLD * top
    ]
    selected.sort(key=lambda a: -scores[a]["score"])
    if not selected:
        selected = ["general"]
    elif len(selected) >= 2 and _PLANNING_RE.search(message):
        selected.insert(0, "general")

    plugin_id = detect_plugin(text, registry) if "hardware" in selected else None
    multi = len(selected) > 1
    query = keywords_from_text(message)
    tasks = []
    for aid in selected:
        spec = registry.agents[aid]
        tasks.append({
            "agent": aid,
            "title": spec.subtask_title if multi else f"{spec.short_name} response",
            "instruction": spec.subtask_instruction.format(message=message) if multi else message,
            "search_query": query,
        })
    caps: list[str] = []
    for aid in selected:
        caps.extend(registry.agents[aid].capabilities[:2])
    return {
        "domain": domain_label(selected, plugin_id, registry),
        "intent": _intent_sentence(message),
        "capabilities": caps[:5],
        "hardware_domain": plugin_id,
        "tasks": tasks,
        "scores": {a: round(v["score"], 1) for a, v in scores.items()},
        "matched": {a: v["hits"][:6] for a, v in scores.items() if v["hits"]},
    }


def _intent_sentence(message: str) -> str:
    first = re.split(r"(?<=[.?!])\s", message.strip(), maxsplit=1)[0]
    return first if len(first) <= 160 else first[:157] + "…"
