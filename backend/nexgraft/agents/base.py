"""Agent (workspace) and plugin specifications.

Each workspace is declared in its own module under `nexgraft/agents/` as an
`AGENT = AgentSpec(...)`. Domain plugins live under `nexgraft/plugins/<agent>/`
as `PLUGIN = PluginSpec(...)`. The registry discovers both automatically, so a
new workspace or engineering domain is added by dropping in one file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

COMMON_PRINCIPLES = (
    "You are part of NEXGRAFT AI, a unified multi-domain AI workspace built from specialised workspaces. "
    "Be accurate and practical. Say clearly when you are unsure. Never invent citations, part numbers, "
    "statistics, tool outputs or results you did not receive. The user controls all real-world actions: "
    "running external software, experiments, fabrication, validation and final decisions. "
    "Format answers in Markdown."
)


@dataclass
class TaskContext:
    """Everything an agent's preparation hook may use for one task."""

    message: str
    instruction: str
    search_query: str
    agent_id: str
    plugin_id: str | None
    attachments: list[dict[str, Any]]
    options: dict[str, Any]
    multi_task: bool = False


@dataclass
class Preparation:
    """Grounding gathered before generation: tool results, sources, notes."""

    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    context_blocks: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


PrepareHook = Callable[[TaskContext], Awaitable[Preparation]]


@dataclass
class AgentSpec:
    id: str
    name: str
    short_name: str
    tagline: str
    description: str
    color: str
    icon: str
    workspace: str  # UI layout: chat | code | research | engineering
    order: int
    system_prompt: str
    capabilities: list[str]
    keywords: dict[str, float]
    knowledge_collections: list[str]
    user_controls: list[str]
    examples: list[str]
    tools: list[str] = field(default_factory=list)
    prepare: PrepareHook | None = None
    uses_plugins: bool = False
    temperature: float | None = None
    boundary: str = ""
    # Used by the keyword router when this workspace handles one part of a larger problem.
    subtask_title: str = ""
    subtask_instruction: str = "Handle the parts of this request that need your expertise: {message}"

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "short_name": self.short_name,
            "tagline": self.tagline,
            "description": self.description,
            "color": self.color,
            "icon": self.icon,
            "workspace": self.workspace,
            "order": self.order,
            "capabilities": self.capabilities,
            "knowledge_collections": self.knowledge_collections,
            "user_controls": self.user_controls,
            "examples": self.examples,
            "tools": self.tools,
            "uses_plugins": self.uses_plugins,
            "boundary": self.boundary,
        }


@dataclass
class PluginSpec:
    id: str
    agent: str
    name: str
    description: str
    icon: str
    keywords: dict[str, float]
    prompt: str
    knowledge_collection: str
    tools: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    order: int = 100

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent": self.agent,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "knowledge_collection": self.knowledge_collection,
            "tools": self.tools,
            "examples": self.examples,
            "order": self.order,
        }
