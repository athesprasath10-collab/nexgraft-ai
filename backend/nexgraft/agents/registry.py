"""Discovers workspaces (agents) and domain plugins at start-up."""

from __future__ import annotations

import importlib
import logging
import pkgutil

from .. import plugins as plugins_pkg
from .base import AgentSpec, PluginSpec

log = logging.getLogger("nexgraft.registry")
agents_pkg_name = __name__.rsplit(".", 1)[0]


class Registry:
    def __init__(self) -> None:
        self.agents: dict[str, AgentSpec] = {}
        self.plugins: dict[str, PluginSpec] = {}

    def load(self) -> "Registry":
        agents_pkg = importlib.import_module(agents_pkg_name)
        for mod in pkgutil.iter_modules(agents_pkg.__path__):
            if mod.name in {"base", "registry", "grounding"}:
                continue
            module = importlib.import_module(f"{agents_pkg_name}.{mod.name}")
            spec = getattr(module, "AGENT", None)
            if isinstance(spec, AgentSpec):
                self.agents[spec.id] = spec
        for group in pkgutil.iter_modules(plugins_pkg.__path__):
            if not group.ispkg:
                continue
            package = importlib.import_module(f"{plugins_pkg.__name__}.{group.name}")
            for mod in pkgutil.iter_modules(package.__path__):
                module = importlib.import_module(f"{package.__name__}.{mod.name}")
                spec = getattr(module, "PLUGIN", None)
                if isinstance(spec, PluginSpec):
                    if spec.agent not in self.agents:
                        log.warning("Plugin %s targets unknown agent %s", spec.id, spec.agent)
                        continue
                    self.plugins[spec.id] = spec
        self.agents = dict(sorted(self.agents.items(), key=lambda kv: kv[1].order))
        self.plugins = dict(sorted(self.plugins.items(), key=lambda kv: kv[1].order))
        return self

    def plugins_for(self, agent_id: str) -> list[PluginSpec]:
        return [p for p in self.plugins.values() if p.agent == agent_id]

    def tools_for(self, agent_id: str, plugin_id: str | None = None) -> list[str]:
        spec = self.agents[agent_id]
        tools = list(spec.tools)
        for p in self.plugins_for(agent_id):
            if plugin_id is None or p.id == plugin_id:
                tools.extend(t for t in p.tools if t not in tools)
        return tools


registry = Registry().load()
