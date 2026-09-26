"""Circuit schematics for Hardware Design AI requests.

When a request is about a circuit that a calculator can draw, the chat model
only picks the circuit and copies the user's values (JSON-schema output). The
calculator then computes the component values and draws the schematic, so the
wiring is always right; the model's job is to explain it. A keyword guard
rejects picks that do not match the request, and every value the request did
not state is labelled as a model choice or a default.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from ..config import settings
from ..llm.ollama import OllamaError, ollama
from ..tools import TOOL_REGISTRY, ToolInputError, ToolSpec, to_markdown
from ..tools.base import format_quantity, parse_quantity, quantities_in_text, split_unit
from .base import Preparation, TaskContext

log = logging.getLogger("nexgraft.schematic")

# Cheap gate so unrelated requests never pay for the extra model call.
HINT = re.compile(
    r"schematic|diagram|circuit|draw|sketch|wiring|\bwire|\bleds?\b|divider|filter|op-?amps?\b|amplifier|transistor|"
    r"\bnpn\b|relay|regulator|\bldo\b|pull-?up|button|debounce",
    re.I,
)
# Circuits no calculator draws; a lookalike schematic would mislead.
NOT_DRAWABLE = re.compile(
    r"\bbuck\b|\bboost\b|\b555\b|h-?bridge|full[- ]bridge|rectifier|inverter|smps|switch(ing|-mode) (power supply|regulator)|dc-?dc",
    re.I,
)
# (must match, must not match) per circuit: the pick has to be what the request is about.
TOPICS: dict[str, tuple[str, str | None]] = {
    "led_resistor": (r"\bleds?\b", r"led strip|strip of leds"),
    "voltage_divider": (r"divid", None),
    "button_pullup": (r"button|push|pull-?up|debounce|tactile", None),
    "transistor_switch": (r"transistor|\bnpn\b|\bbjt\b|relay|solenoid|motor|led strip|lamp|buzzer|\bload\b|switch|driv", r"mosfet|\bfet\b|\bpnp\b|high-side"),
    "rc_filter": (r"filter|\brc\b|low-?pass|high-?pass|cut-?off", r"band-?pass|notch|sallen|butterworth|active filter|\blc\b"),
    "opamp_inverting": (r"op-?amp|operational|amplif|gain", None),
    "opamp_noninverting": (r"op-?amp|operational|amplif|gain", None),
    "linear_regulator": (r"regulat|\bldo\b|power supply|step.?down|\d(\.\d)? ?v to \d", None),
}

_EXAMPLES: list[tuple[str, dict[str, Any]]] = [
    (
        "Draw the circuit to light a red LED from a 5 V Arduino pin at 15 mA.",
        {"circuit": "led_resistor", "values": {"supply_v": "5 V", "forward_v": "2 V", "current_ma": "15 mA"}},
    ),
    (
        "Switch a 12 V relay coil that draws 70 mA from an ESP32 pin.",
        {"circuit": "transistor_switch", "values": {"supply_v": "12 V", "load_current_ma": "70 mA", "logic_v": "3.3 V", "load": "inductive (relay, motor, solenoid)"}},
    ),
    (
        "Turn a 12 V LED strip on and off from a Raspberry Pi.",
        {"circuit": "transistor_switch", "values": {"supply_v": "12 V", "logic_v": "3.3 V", "load": "resistive (lamp, LED strip, heater)"}},
    ),
    (
        "Low-pass filter with a 1 kHz cutoff for a sensor signal.",
        {"circuit": "rc_filter", "values": {"kind": "low-pass", "cutoff_hz": "1 kHz"}},
    ),
    (
        "Schematic for an amplifier with a gain of 20.",
        {"circuit": "opamp_noninverting", "values": {"gain": "20"}},
    ),
    ("Which sensors suit a wearable heart-rate monitor?", {"circuit": "none"}),
    ("What should I check before ordering the PCB for my circuit?", {"circuit": "none"}),
]


def circuit_tools() -> list[ToolSpec]:
    return [t for t in TOOL_REGISTRY.values() if t.schematic]


def picker_schema(tools: list[ToolSpec]) -> dict[str, Any]:
    """One branch per circuit, so the model only sees that circuit's values."""
    branches: list[dict[str, Any]] = [
        {"type": "object", "properties": {"circuit": {"type": "string", "enum": ["none"]}}, "required": ["circuit"]}
    ]
    for t in tools:
        values = {
            p.name: {"type": "string", "enum": p.options} if p.options else {"type": "string", "maxLength": 16}
            for p in t.params
        }
        branches.append({
            "type": "object",
            "properties": {"circuit": {"type": "string", "enum": [t.id]}, "values": {"type": "object", "properties": values}},
            "required": ["circuit", "values"],
        })
    return {"anyOf": branches}


def _describe(tool: ToolSpec) -> str:
    params = []
    for p in tool.params:
        detail = "one of: " + " | ".join(p.options) if p.options else p.unit
        params.append(f"{p.name} ({p.label}{', ' + detail if detail else ''})")
    return f"- {tool.id}: {tool.name}. {tool.description} Values: {', '.join(params)}."


def picker_messages(text: str, tools: list[ToolSpec]) -> list[dict[str, str]]:
    system = (
        "You choose a circuit schematic for NEXGRAFT Hardware Design AI. Circuits it can draw:\n"
        + "\n".join(_describe(t) for t in tools)
        + "\n\nRules:\n"
        "1. Pick the circuit that the request asks to design, draw, wire or explain. Pick \"none\" when none of these "
        "circuits is the subject: general questions, component or sensor selection, PCB layout, mechanical or civil "
        "topics, and other circuits such as buck converters, H-bridges, 555 timers or complete systems.\n"
        "2. Copy only the values the request gives, with their units (e.g. \"10k\", \"100 nF\", \"5 V\", \"20 mA\"). "
        "Common facts count as given: Arduino Uno pins are 5 V; ESP32, Raspberry Pi and STM32 pins are 3.3 V; a red "
        "LED drops about 2 V and a blue, white or green one about 3 V. Never invent other values; leave them out.\n"
        "3. Reply with JSON only."
    )
    messages = [{"role": "system", "content": system}]
    for question, answer in _EXAMPLES:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": json.dumps(answer)})
    messages.append({"role": "user", "content": text})
    return messages


def on_topic(tool_id: str, text: str) -> bool:
    must, must_not = TOPICS.get(tool_id, (None, None))
    if NOT_DRAWABLE.search(text) or (must_not and re.search(must_not, text, re.I)):
        return False
    return must is None or bool(re.search(must, text, re.I))


def _stated(value: float, base: str | None, stated: list[tuple[float, str | None]]) -> bool:
    """True when the request states this quantity: same number (after SI prefixes) and no conflicting unit."""
    return any(math.isclose(abs(value), q, rel_tol=1e-6) and (b is None or base is None or b == base) for q, b in stated)


def _may_choose(p, text: str) -> bool:
    """Whether a value the request did not state may still come from the model: a required voltage (logic
    levels and LED drops are common facts), or a feature the request names, e.g. 'debounce'."""
    first_word = re.split(r"[\s(]", p.label.lower())[0]
    return (p.unit == "V" and p.required) or first_word in text.lower()


def _fmt(p, value: Any) -> str:
    return f"{p.label} = {format_quantity(value, p.unit) if isinstance(value, (int, float)) else value}"


async def add_schematic(ctx: TaskContext, prep: Preparation) -> None:
    """Draw a schematic when the request is about one of the drawable circuits."""
    if ctx.options.get("diagrams") is False:
        return
    text = ctx.message if ctx.instruction.strip() in ("", ctx.message.strip()) else f"{ctx.message}\n\n(Focus: {ctx.instruction})"
    if not HINT.search(text) or NOT_DRAWABLE.search(text):
        return
    tools = circuit_tools()
    try:
        model = await ollama.resolve_chat_model(ctx.options.get("model") or settings.model or None)
        raw = await ollama.chat_json(model, picker_messages(text[:4000], tools), picker_schema(tools),
                                     options={"num_predict": 200}, timeout=settings.analyzer_timeout)
    except OllamaError as exc:
        log.warning("Circuit picker unavailable: %s", exc)
        return
    if not isinstance(raw, dict):
        return
    tool = TOOL_REGISTRY.get(str(raw.get("circuit") or ""))
    if tool is None or not tool.schematic or not on_topic(tool.id, text):
        return

    params = {p.name: p for p in tool.params}
    stated = quantities_in_text(text)
    values: dict[str, Any] = {}
    chosen: list[str] = []  # numbers the model supplied that the request never stated
    for key, value in (raw.get("values") if isinstance(raw.get("values"), dict) else {}).items():
        p = params.get(key)
        if p is None or not str(value).strip():
            continue
        if p.type == "number":
            try:
                value = parse_quantity(value, p.unit)
            except ValueError:
                continue  # unusable value: the default applies and is reported below
            scale, base = split_unit(p.unit)
            if not _stated(value * scale, base, stated):
                if not _may_choose(p, text):
                    continue  # small models invent values; the calculator's default is the better guess
                chosen.append(key)
        values[key] = value

    try:
        output = await tool.execute(values)
    except ToolInputError as exc:
        try:  # the model's own choices may be what does not fit; retry with the request's values only
            if not chosen:
                raise
            values = {k: v for k, v in values.items() if k not in chosen}
            chosen = []
            output = await tool.execute(values)
        except ToolInputError:
            prep.notes.append(f"No {tool.name} schematic was drawn: {exc}")
            return

    labels = []
    if chosen:
        labels.append("Chosen by the model, not stated in your request: " + "; ".join(_fmt(params[k], values[k]) for k in chosen) + ".")
    defaults = [
        _fmt(p, p.default)
        for p in tool.params
        if p.name not in values and p.default is not None and not (p.overridden_by and values.get(p.overridden_by))
    ]
    if defaults:
        labels.append("Default values used: " + "; ".join(defaults) + ".")
    if labels:
        labels.append(f"Adjust any of them in the {tool.name} calculator (Calculators panel).")
        output["notes"] = [" ".join(labels), *output.get("notes", [])]

    prep.tool_calls.append({"tool": tool.id, "name": tool.name, "input": values, "output": output})
    prep.context_blocks.append(
        "The NEXGRAFT circuit tool drew this schematic, and the user sees it above your answer. Its values are "
        "computed, not estimated, so use them exactly:\n"
        + to_markdown(output["schematic"]["title"], output)
        + "\n\nBegin with a '## How the circuit works' section that walks through the schematic part by part, by "
        "designator (R1, D1, Q1 …): what each part does and why it has its value. Then continue with your usual "
        "sections. If the notes list default or model-chosen values, mention them once, in one sentence, as "
        "assumptions to check. Do not redraw the circuit as text or ASCII art."
    )
