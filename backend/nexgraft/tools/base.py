"""Tool specification shared by all workspaces.

A tool is a deterministic function with a declared parameter schema. The UI
renders a form from `params`, the user runs it explicitly, and agents may also
call selected tools automatically (for example, sequence statistics when a DNA
sequence appears in a bioinformatics request). Tool results are real computed
values, never LLM guesses.
"""

from __future__ import annotations

import inspect
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable


class ToolInputError(ValueError):
    """Raised for invalid user input; the message is shown in the UI."""


@dataclass
class Param:
    name: str
    label: str
    type: str = "number"  # number | string | text | select | boolean
    unit: str = ""
    default: Any = None
    options: list[str] | None = None
    required: bool = True
    help: str = ""
    min: float | None = None
    max: float | None = None


@dataclass
class ToolSpec:
    id: str
    name: str
    description: str
    agent: str
    run: Callable[..., dict[str, Any] | Awaitable[dict[str, Any]]]
    params: list[Param] = field(default_factory=list)
    plugin: str | None = None
    category: str = ""
    formula: str = ""
    requires_network: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "agent": self.agent,
            "plugin": self.plugin,
            "category": self.category,
            "formula": self.formula,
            "requires_network": self.requires_network,
            "params": [asdict(p) for p in self.params],
        }

    def coerce(self, raw: dict[str, Any]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for p in self.params:
            v = raw.get(p.name, p.default)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                if p.required and p.default is None:
                    raise ToolInputError(f"'{p.label}' is required.")
                values[p.name] = p.default
                continue
            if p.type == "number":
                try:
                    v = float(v)
                except (TypeError, ValueError) as exc:
                    raise ToolInputError(f"'{p.label}' must be a number.") from exc
                if p.min is not None and v < p.min:
                    raise ToolInputError(f"'{p.label}' must be ≥ {p.min}.")
                if p.max is not None and v > p.max:
                    raise ToolInputError(f"'{p.label}' must be ≤ {p.max}.")
            elif p.type == "boolean":
                v = v if isinstance(v, bool) else str(v).lower() in {"1", "true", "yes", "on"}
            elif p.type == "select":
                if p.options and v not in p.options:
                    raise ToolInputError(f"'{p.label}' must be one of: {', '.join(p.options)}.")
            else:
                v = str(v)
            values[p.name] = v
        return values

    async def execute(self, raw: dict[str, Any]) -> dict[str, Any]:
        values = self.coerce(raw)
        result = self.run(**values)
        if inspect.isawaitable(result):
            result = await result
        return result


def result(summary: str, rows: list[tuple[str, Any, str]] | None = None, **extra: Any) -> dict[str, Any]:
    """Standard tool output: a one-line summary plus labelled values."""
    out: dict[str, Any] = {
        "summary": summary,
        "results": [
            {"label": label, "value": _fmt(value), "unit": unit} for label, value, unit in (rows or [])
        ],
    }
    out.update({k: v for k, v in extra.items() if v not in (None, [], {})})
    return out


def _fmt(value: Any) -> Any:
    if isinstance(value, float):
        if value == 0:
            return 0
        magnitude = abs(value)
        if magnitude >= 1e6 or magnitude < 1e-3:
            return f"{value:.4g}"
        return round(value, 4) if magnitude < 10 else round(value, 2)
    return value


def to_markdown(tool_name: str, output: dict[str, Any]) -> str:
    """Render a tool result as compact text for inclusion in an LLM prompt."""
    lines = [f"### {tool_name}", output.get("summary", "")]
    for row in output.get("results", []):
        unit = f" {row['unit']}" if row.get("unit") else ""
        lines.append(f"- {row['label']}: {row['value']}{unit}")
    for key in ("sequence_preview", "alignment", "notes"):
        if output.get(key):
            val = output[key]
            lines.append(f"{key.replace('_', ' ').title()}: {val if isinstance(val, str) else '; '.join(map(str, val))}")
    for w in output.get("warnings", []):
        lines.append(f"- Warning: {w}")
    return "\n".join(line for line in lines if line)
