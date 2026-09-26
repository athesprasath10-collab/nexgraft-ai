"""Schematic drawings for the circuit calculators, rendered to SVG with schemdraw.

Each function takes the already computed, formatted values and returns
{"svg", "title", "caption"}. Layouts are fixed per circuit type, so every
wire in a drawing is correct by construction; only the labels change.
"""

from __future__ import annotations

import re
from typing import Any

import schemdraw
import schemdraw.elements as elm

schemdraw.use("svg")

UNIT = 3.0
FONT = 13


def _pad_viewbox(svg: str, x_pad: float = 36, y_pad: float = 10) -> str:
    """schemdraw estimates text width; browsers' fonts run wider, so give labels room."""
    m = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', svg)
    if not m:
        return svg
    x, y, w, h = (float(v) for v in m.groups())
    w, h = w + 2 * x_pad, h + 2 * y_pad
    svg = svg.replace(m.group(0), f'viewBox="{x - x_pad:.1f} {y - y_pad:.1f} {w:.1f} {h:.1f}"', 1)
    svg = re.sub(r'height="[\d.]+pt"', f'height="{h:.1f}pt"', svg, count=1)
    return re.sub(r'width="[\d.]+pt"', f'width="{w:.1f}pt"', svg, count=1)


def _render(d: schemdraw.Drawing, title: str, caption: str) -> dict[str, Any]:
    svg = d.get_imagedata("svg")
    if isinstance(svg, bytes):
        svg = svg.decode("utf-8")
    svg = re.sub(r"(\d+\.\d{2})\d+", r"\1", svg)  # trim float noise: smaller files, same drawing
    return {"svg": _pad_viewbox(svg), "title": title, "caption": caption}


def _drawing() -> schemdraw.Drawing:
    d = schemdraw.Drawing(show=False)
    d.config(unit=UNIT, fontsize=FONT, lw=1.6)
    return d


def led(supply: str, resistor: str, led_label: str, current: str) -> dict[str, Any]:
    with _drawing() as d:
        src = elm.SourceV().up().label(f"V1\n{supply}", loc="bottom", ofst=0.25)
        r1 = elm.Resistor().right().label(f"R1\n{resistor}")
        elm.CurrentLabel(top=False, length=1.2).at(r1).label(f"I = {current}", loc="bottom")
        elm.LED().down().label(f"D1\n{led_label}", loc="bottom")
        elm.Line().left().to(src.start)
        elm.Ground().at(src.start)
    return _render(d, "LED with series resistor", "V1 drives current through R1, which sets the LED current; D1's anode faces R1.")


def voltage_divider(vin: str, r1: str, r2: str, vout: str, load: str | None) -> dict[str, Any]:
    with _drawing() as d:
        src = elm.SourceV().up().length(UNIT * 2).label(f"V1\n{vin}", loc="bottom", ofst=0.25)
        elm.Line().right()
        elm.Resistor().down().label(f"R1\n{r1}", loc="bottom")
        node = elm.Dot()
        elm.Resistor().down().label(f"R2\n{r2}", loc="bottom")
        bottom = d.here
        elm.Line().left().to(src.start)
        elm.Ground().at(src.start)
        out = elm.Line().right(UNIT * (1.4 if load else 1)).at(node.center)
        elm.Dot(open=True).label(f"Vout\n{vout}", loc="right")
        if load:
            elm.Resistor().down().at((out.end[0] - UNIT * 0.7, out.end[1])).label(f"RL\n{load}", loc="bottom")
            elm.Line().left().to(bottom)
            elm.Dot().at(bottom)
            elm.Dot().at((out.end[0] - UNIT * 0.7, out.end[1]))
    return _render(d, "Resistive voltage divider", "Vout is taken from the junction of R1 and R2" + (" and feeds the load RL." if load else "."))


def rc_filter(kind: str, r: str, c: str, fc: str) -> dict[str, Any]:
    low = kind == "low-pass"
    with _drawing() as d:
        elm.Dot(open=True).label("Vin", loc="left")
        (elm.Resistor if low else elm.Capacitor)().right().label(f"R1\n{r}" if low else f"C1\n{c}")
        node = elm.Dot()
        (elm.Capacitor if low else elm.Resistor)().down().label(f"C1\n{c}" if low else f"R1\n{r}", loc="bottom")
        elm.Ground()
        elm.Line().right().at(node.center)
        elm.Dot(open=True).label(f"Vout\nfc = {fc}", loc="right")
    what = "passes frequencies below" if low else "passes frequencies above"
    return _render(d, f"RC {kind} filter", f"First-order RC {kind}: {what} fc = {fc}.")


def opamp_inverting(rin: str, rf: str, gain: str) -> dict[str, Any]:
    with _drawing() as d:
        op = elm.Opamp(leads=True).label("U1", loc="center", ofst=0)
        elm.Line().down(UNIT / 4).at(op.in2)
        elm.Ground(lead=False)
        elm.Dot().at(op.in1)
        elm.Resistor().at(op.in1).left().label(f"R1 (Rin)\n{rin}", loc="bottom")
        elm.Dot(open=True).label("Vin", loc="left")
        elm.Line().up(UNIT / 2).at(op.in1)
        elm.Resistor().tox(op.out).label(f"R2 (Rf)\n{rf}")
        elm.Line().toy(op.out)
        elm.Dot()
        elm.Line().right(UNIT / 3).at(op.out)
        elm.Dot(open=True).label(f"Vout\nG = {gain}", loc="right")
    return _render(d, "Inverting op-amp amplifier", f"Gain = −R2/R1 = {gain}. The + input is at ground (dual supply).")


def opamp_noninverting(rg: str, rf: str, gain: str) -> dict[str, Any]:
    with _drawing() as d:
        op = elm.Opamp(leads=True).flip().label("U1", loc="center", ofst=0)
        elm.Line().left(UNIT / 3).at(op.in2)
        elm.Dot(open=True).label("Vin", loc="left")
        elm.Line().down(UNIT / 2).at(op.in1)
        node = elm.Dot()
        elm.Resistor().tox(op.out).label(f"R2 (Rf)\n{rf}", loc="bottom")
        elm.Line().toy(op.out)
        elm.Dot()
        elm.Resistor().down().at(node.center).label(f"R1 (Rg)\n{rg}", loc="bottom")
        elm.Ground()
        elm.Line().right(UNIT / 3).at(op.out)
        elm.Dot(open=True).label(f"Vout\nG = {gain}", loc="right")
    return _render(d, "Non-inverting op-amp amplifier", f"Gain = 1 + R2/R1 = {gain}.")


def transistor_switch(supply: str, load: str, rb: str, rbe: str, logic: str, inductive: bool, diode: str) -> dict[str, Any]:
    with _drawing() as d:
        elm.Dot(open=True).label(f"GPIO\n{logic}", loc="left")
        elm.Resistor().right().label(f"R1\n{rb}")
        base = elm.Dot()
        elm.Line().right(UNIT / 2)
        q = elm.BjtNpn(circle=True).anchor("base").label("Q1", loc="right")
        r2 = elm.Resistor().down().at(base.center).label(f"R2\n{rbe}", loc="top")
        elm.Line().down().at(q.emitter).toy(r2.end)
        emitter_gnd = d.here
        elm.Line().left().to(r2.end)
        elm.Dot().at(emitter_gnd)
        elm.Ground().at(emitter_gnd)
        elm.Line().up(UNIT / 4).at(q.collector)
        collector = elm.Dot() if inductive else None
        if inductive:
            elm.Inductor2(loops=3).up().label(f"K1 coil\n{load}", loc="bottom")
        else:
            elm.RBox().up().label(f"Load\n{load}", loc="bottom")
        top = elm.Dot() if inductive else None
        elm.Vdd().label(supply)
        if inductive and top and collector:
            elm.Line().right(UNIT * 0.7).at(top.center)
            elm.Diode().down().toy(collector.center).reverse().label(f"D1\n{diode}", loc="bottom")
            elm.Line().left().to(collector.center)
    caption = "Q1 switches the low side of the load; R2 keeps Q1 off while the GPIO floats."
    if inductive:
        caption += " D1 clamps the coil's turn-off voltage spike."
    return _render(d, "NPN low-side transistor switch", caption)


def linear_regulator(vin: str, vout: str, cin: str, cout: str, label: str, current: str) -> dict[str, Any]:
    with _drawing() as d:
        elm.Dot(open=True).label(f"Vin\n{vin}", loc="left")
        elm.Line().right(UNIT * 0.8)
        n_in = elm.Dot()
        reg = elm.VoltageRegulator().right().anchor("in").label(f"U1\n{label}", loc="top")
        elm.Capacitor().down().at(n_in.center).label(f"C1\n{cin}", loc="bottom")
        gnd_left = d.here
        elm.Line().down(UNIT / 2).at(reg.gnd).toy(gnd_left)
        elm.Ground()
        elm.Line().right(UNIT * 0.8).at(reg.out)
        n_out = elm.Dot()
        elm.Capacitor().down().label(f"C2\n{cout}", loc="bottom")
        gnd_mid = (reg.gnd[0], gnd_left[1])
        elm.Line().left().to(gnd_mid)
        elm.Line().left().at(gnd_mid).to(gnd_left)
        elm.Dot().at(gnd_mid)
        elm.Line().right(UNIT * 0.8).at(n_out.center)
        elm.Dot(open=True).label(f"Vout\n{vout}\n{current}", loc="right")
    return _render(d, "Linear regulator (LDO)", "C1 and C2 sit close to U1's pins; their type and value come from the regulator's datasheet.")


def button_pullup(vcc: str, r: str, cap: str | None) -> dict[str, Any]:
    with _drawing() as d:
        elm.Vdd().label(vcc)
        elm.Resistor().down().label(f"R1\n{r}", loc="bottom")
        node = elm.Dot()
        elm.Button().down().label("S1", loc="bottom")
        gnd = d.here
        elm.Ground()
        elm.Line().right(UNIT * (1.4 if cap else 1)).at(node.center)
        elm.Dot(open=True).label("GPIO\n(input)", loc="right")
        if cap:
            x = node.center[0] + UNIT * 0.8
            elm.Dot().at((x, node.center[1]))
            elm.Capacitor().down().at((x, node.center[1])).label(f"C1\n{cap}", loc="bottom").toy(gnd)
            elm.Line().left().to(gnd)
            elm.Dot().at(gnd)
    caption = "The pin reads HIGH through R1 when S1 is open, and LOW when S1 is pressed."
    if cap:
        caption += " C1 with R1 filters contact bounce."
    return _render(d, "Push-button with pull-up resistor", caption)
