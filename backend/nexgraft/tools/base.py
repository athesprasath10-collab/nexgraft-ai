"""Tool specification shared by all workspaces.

A tool is a deterministic function with a declared parameter schema. The UI
renders a form from `params`, the user runs it explicitly, and agents may also
call selected tools automatically (for example, sequence statistics when a DNA
sequence appears in a bioinformatics request). Tool results are real computed
values, never LLM guesses.
"""

from __future__ import annotations

import inspect
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable


class ToolInputError(ValueError):
    """Raised for invalid user input; the message is shown in the UI."""


_PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "μ": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
_BASE_UNIT = {
    "v": "V", "volt": "V", "volts": "V", "a": "A", "amp": "A", "amps": "A", "ω": "Ω", "ohm": "Ω", "ohms": "Ω", "r": "Ω",
    "f": "F", "farad": "F", "hz": "Hz", "w": "W", "watt": "W", "watts": "W", "s": "s", "h": "H",
}
_NUMBER = re.compile(r"([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*)")
_RKM = re.compile(r"(\d+)([pnuµμmkKMGRV])(\d+)\s*(.*)")  # 4k7 = 4.7k, 3V3 = 3.3 V
_QUANTITY = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?:([pnuµμmkKMGRV])(\d+))?\s*([A-Za-zΩµμ]+)?")


def quantities_in_text(text: str) -> list[tuple[float, str | None]]:
    """Every number in free text with its base unit when one follows: '300 mA' -> (0.3, 'A'), '10k' -> (10000, None)."""
    found: list[tuple[float, str | None]] = []
    for whole, mark, frac, unit in _QUANTITY.findall(text):
        number = float(f"{whole}.{frac}") * (1.0 if mark in "RV" else _PREFIX[mark]) if mark else float(whole)
        split = _split_unit(unit) if unit else (1.0, None)
        if mark == "V" and not unit:
            split = (1.0, "V")
        scale, base = split if split else (1.0, None)
        found.append((number * scale, base))
    return found


def split_unit(unit: str) -> tuple[float, str | None]:
    """'mA' -> (1e-3, 'A'), 'Ω' -> (1, 'Ω'), 'V/V' or '°C/W' -> (1, None)."""
    return _split_unit(unit.strip()) or (1.0, None)


def _split_unit(text: str) -> tuple[float, str | None] | None:
    """'kΩ' -> (1e3, 'Ω'), 'nF' -> (1e-9, 'F'), 'k' -> (1e3, None), '' -> (1, None)."""
    if not text:
        return 1.0, None
    if text.lower() in _BASE_UNIT:
        return 1.0, _BASE_UNIT[text.lower()]
    if text.lower().startswith("meg"):
        rest = text[3:]
        return (1e6, _BASE_UNIT.get(rest.lower())) if not rest or rest.lower() in _BASE_UNIT else None
    if text[0] in _PREFIX and (len(text) == 1 or text[1:].lower() in _BASE_UNIT):
        return _PREFIX[text[0]], _BASE_UNIT.get(text[1:].lower()) if len(text) > 1 else None
    return None


def format_quantity(value: float, unit: str = "") -> str:
    """10000, 'Ω' -> '10 kΩ'; 1e-7, 'F' -> '100 nF'; 20, 'mA' -> '20 mA'."""
    if unit in ("V", "A", "Ω", "F", "Hz", "W", "s") and value:
        for factor, prefix in ((1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")):
            if abs(value) >= factor:
                return f"{value / factor:.3g} {prefix}{unit}"
    return f"{value:g} {unit}".strip()


def parse_quantity(raw: Any, unit: str = "") -> float:
    """Parse '10k', '4k7', '100 nF', '20 mA', '3V3' or a plain number into the parameter's unit."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip().replace("\u2212", "-").replace("\u00a0", " ")
    try:
        return float(text)
    except ValueError:
        pass
    rkm = _RKM.fullmatch(text)
    if rkm:
        whole, mark, frac, rest = rkm.groups()
        scale = 1.0 if mark in "RV" else _PREFIX[mark]
        number, tail = float(f"{whole}.{frac}") * scale, rest.strip() or ("V" if mark == "V" else "")
    else:
        m = _NUMBER.fullmatch(text)
        if not m:
            raise ValueError(text)
        number, tail = float(m.group(1)), m.group(2).strip()
    if tail == unit.strip():
        return number
    split = _split_unit(tail)
    if split is None:
        raise ValueError(text)
    scale, base = split
    target = _split_unit(unit.strip())
    if target is None:  # a unit the parser does not know, e.g. "V/V" or "°C/W"
        if base:
            raise ValueError(text)
        return number * scale
    target_scale, target_base = target
    if base and target_base and base != target_base:
        raise ValueError(text)
    return number * scale / target_scale


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
    overridden_by: str | None = None  # another parameter that, when set, replaces this one


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
    schematic: bool = False  # the output includes a circuit drawing

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
            "schematic": self.schematic,
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
                    v = parse_quantity(v, p.unit)
                except (TypeError, ValueError) as exc:
                    unit = f" in {p.unit}" if p.unit else ""
                    raise ToolInputError(f"'{p.label}' must be a number{unit} (e.g. 4.7, 10k or 100n).") from exc
                if p.min is not None and v < p.min:
                    raise ToolInputError(f"'{p.label}' must be ≥ {p.min}.")
                if p.max is not None and v > p.max:
                    raise ToolInputError(f"'{p.label}' must be ≤ {p.max}.")
            elif p.type == "boolean":
                v = v if isinstance(v, bool) else str(v).lower() in {"1", "true", "yes", "on"}
            elif p.type == "select":
                if p.options and v not in p.options:
                    wanted = str(v).strip().lower()
                    close = [o for o in p.options if wanted and (o.lower().startswith(wanted) or wanted in o.lower())]
                    if len(close) != 1:
                        raise ToolInputError(f"'{p.label}' must be one of: {', '.join(p.options)}.")
                    v = close[0]
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
    if output.get("parts"):
        lines.append("Parts (designators as drawn in the schematic):")
        lines.extend(f"- {p['ref']}: {p['value']} — {p['description']}" for p in output["parts"])
    for key in ("sequence_preview", "alignment", "notes"):
        if output.get(key):
            val = output[key]
            lines.append(f"{key.replace('_', ' ').title()}: {val if isinstance(val, str) else '; '.join(map(str, val))}")
    for w in output.get("warnings", []):
        lines.append(f"- Warning: {w}")
    return "\n".join(line for line in lines if line)
