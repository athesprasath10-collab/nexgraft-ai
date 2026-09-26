"""Engineering calculators used by Hardware Design AI domain plugins.

Every calculator uses a standard textbook formula shown in `formula`. They are
first-pass design aids; the user validates results against datasheets, codes
and their own analysis.
"""

from __future__ import annotations

import math

from . import circuits
from .base import Param, ToolInputError, ToolSpec, result

E6 = [1.0, 1.5, 2.2, 3.3, 4.7, 6.8]
E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]
E24 = [1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1]


def standard_value(value: float, series: list[float] = E12, mode: str = "up") -> float:
    """Standard component value from an E-series: the next one up, down, or the nearest."""
    if value <= 0:
        raise ToolInputError("Component values must be positive.")
    decade = 10 ** math.floor(math.log10(value))
    candidates = [float(f"{b * decade * k:.6g}") for k in (0.1, 1, 10) for b in series]
    if mode == "up":
        return min(c for c in candidates if c >= value * (1 - 1e-9))
    if mode == "down":
        return max(c for c in candidates if c <= value * (1 + 1e-9))
    return min(candidates, key=lambda c: abs(math.log(c / value)))


def next_standard_resistor(value: float, series: list[float] = E12) -> float:
    """Smallest standard value ≥ value."""
    if value <= 0:
        raise ToolInputError("Resistance must be positive.")
    return standard_value(value, series, "up")


def _part(ref: str, value: str, description: str) -> dict:
    return {"ref": ref, "value": value, "description": description}


def _si(value: float, unit: str) -> str:
    prefixes = [(1e9, "G"), (1e6, "M"), (1e3, "k"), (1, ""), (1e-3, "m"), (1e-6, "µ"), (1e-9, "n"), (1e-12, "p")]
    for factor, prefix in prefixes:
        if abs(value) >= factor:
            return f"{value / factor:.3g} {prefix}{unit}"
    return f"{value:.3g} {unit}"


# ---------------------------------------------------------------- electronics
def ohms_law(voltage_v: float | None = None, current_a: float | None = None, resistance_ohm: float | None = None) -> dict:
    given = {k: v for k, v in {"V": voltage_v, "I": current_a, "R": resistance_ohm}.items() if v not in (None, 0.0)}
    if len(given) < 2:
        raise ToolInputError("Enter any two of voltage, current and resistance.")
    v, i, r = voltage_v, current_a, resistance_ohm
    if "V" not in given:
        v = i * r
    elif "I" not in given:
        i = v / r
    elif "R" not in given:
        r = v / i
    power = v * i
    return result(
        f"V = {v:.4g} V, I = {_si(i, 'A')}, R = {_si(r, 'Ω')}, P = {_si(power, 'W')}",
        [("Voltage", v, "V"), ("Current", i, "A"), ("Resistance", r, "Ω"), ("Power", power, "W")],
    )


def voltage_divider(vin_v: float, r1_ohm: float, r2_ohm: float, load_ohm: float | None = None, target_vout_v: float | None = None) -> dict:
    if r1_ohm <= 0 or r2_ohm <= 0:
        raise ToolInputError("Resistances must be positive.")
    target_rows = []
    if target_vout_v:
        if not 0 < target_vout_v < vin_v:
            raise ToolInputError("The target Vout must be between 0 V and the input voltage.")
        r2_exact = r1_ohm * target_vout_v / (vin_v - target_vout_v)
        r2_ohm = standard_value(r2_exact, E24, "nearest")
        target_rows = [("R2 for the target (exact)", r2_exact, "Ω"), ("R2, nearest E24", r2_ohm, "Ω")]
    r2_eff = r2_ohm if not load_ohm else (r2_ohm * load_ohm) / (r2_ohm + load_ohm)
    vout = vin_v * r2_eff / (r1_ohm + r2_eff)
    current = vin_v / (r1_ohm + r2_eff)
    rows = [
        ("Vout", vout, "V"),
        *target_rows,
        ("Divider current", current * 1000, "mA"),
        ("Power in R1", current**2 * r1_ohm * 1000, "mW"),
        ("Thevenin output resistance", r1_ohm * r2_ohm / (r1_ohm + r2_ohm), "Ω"),
    ]
    warnings = []
    if load_ohm:
        unloaded = vin_v * r2_ohm / (r1_ohm + r2_ohm)
        rows.insert(1, ("Vout without load", unloaded, "V"))
        if abs(unloaded - vout) / unloaded > 0.05:
            warnings.append("Load changes Vout by more than 5% — consider a buffer or lower divider resistances.")
    parts = [
        _part("V1", _si(vin_v, "V"), "Input voltage source"),
        _part("R1", _si(r1_ohm, "Ω"), "Top resistor, from Vin to the output node"),
        _part("R2", _si(r2_ohm, "Ω"), "Bottom resistor, from the output node to ground"),
    ]
    if load_ohm:
        parts.append(_part("RL", _si(load_ohm, "Ω"), "The load connected to Vout"))
    schematic = circuits.voltage_divider(
        _si(vin_v, "V"), _si(r1_ohm, "Ω"), _si(r2_ohm, "Ω"), _si(vout, "V"), _si(load_ohm, "Ω") if load_ohm else None
    )
    return result(f"Vout = {vout:.4g} V", rows, warnings=warnings, parts=parts, schematic=schematic)


def led_resistor(supply_v: float, forward_v: float, current_ma: float) -> dict:
    if supply_v <= forward_v:
        raise ToolInputError("Supply voltage must exceed the LED forward voltage.")
    if current_ma <= 0:
        raise ToolInputError("LED current must be positive.")
    i = current_ma / 1000
    r = (supply_v - forward_v) / i
    r_std = next_standard_resistor(r)
    i_actual = (supply_v - forward_v) / r_std
    p = i_actual**2 * r_std
    rating = next(x for x in (0.063, 0.1, 0.125, 0.25, 0.5, 1.0, 2.0, 5.0) if x >= 2 * p) if 2 * p <= 5 else None
    r_label = _si(r_std, "Ω") + (f", {rating:g} W" if rating else "")
    parts = [
        _part("V1", _si(supply_v, "V"), "Supply (battery, USB or a microcontroller pin driven high)"),
        _part("R1", r_label, "Current-limiting resistor"),
        _part("D1", f"LED, Vf ≈ {forward_v:g} V", f"Anode towards R1, cathode (flat side, shorter leg) to ground; rated ≥ {current_ma:g} mA"),
    ]
    schematic = circuits.led(_si(supply_v, "V"), r_label, f"LED, Vf {forward_v:g} V", f"{i_actual * 1000:.1f} mA")
    return result(
        f"Use {_si(r_std, 'Ω')} (E12) → {i_actual * 1000:.1f} mA",
        [
            ("Calculated resistance", r, "Ω"),
            ("Next E12 value", r_std, "Ω"),
            ("Actual LED current", i_actual * 1000, "mA"),
            ("Resistor dissipation", p * 1000, "mW"),
            ("Suggested power rating (2× margin)", f"{rating} W" if rating else "> 5 W — reconsider design", ""),
        ],
        parts=parts,
        schematic=schematic,
    )


def rc_filter(resistance_ohm: float, capacitance_f: float, kind: str = "low-pass", cutoff_hz: float | None = None) -> dict:
    if resistance_ohm <= 0 or capacitance_f <= 0:
        raise ToolInputError("R and C must be positive.")
    target_rows = []
    if cutoff_hz:
        if cutoff_hz <= 0:
            raise ToolInputError("The target cutoff frequency must be positive.")
        c_exact = 1 / (2 * math.pi * resistance_ohm * cutoff_hz)
        capacitance_f = standard_value(c_exact, E12, "nearest")
        target_rows = [("C for the target (exact)", c_exact * 1e9, "nF"), ("C, nearest E12", capacitance_f * 1e9, "nF")]
    tau = resistance_ohm * capacitance_f
    fc = 1 / (2 * math.pi * tau)
    low = kind == "low-pass"
    parts = [
        _part("R1", _si(resistance_ohm, "Ω"), "Series resistor" if low else "Resistor to ground"),
        _part("C1", _si(capacitance_f, "F"), "Capacitor to ground" if low else "Series (coupling) capacitor"),
    ]
    schematic = circuits.rc_filter(kind, _si(resistance_ohm, "Ω"), _si(capacitance_f, "F"), _si(fc, "Hz"))
    return result(
        f"{kind}: fc = {_si(fc, 'Hz')}, τ = {_si(tau, 's')}",
        [
            ("Cutoff frequency (−3 dB)", fc, "Hz"),
            *target_rows,
            ("Time constant τ", tau, "s"),
            ("Rise time 10–90% (≈2.2τ)", 2.2 * tau, "s"),
            ("Settling to 99% (≈4.6τ)", 4.6 * tau, "s"),
            ("Roll-off", "20 dB per decade " + ("above" if low else "below") + " fc", ""),
        ],
        notes=["The source should have a low output impedance and the load a high input impedance compared with R1, or fc shifts."],
        parts=parts,
        schematic=schematic,
    )


# ---------------------------------------------------------- circuit schematics
def opamp_inverting(gain: float, rin_ohm: float = 10000, gbw_hz: float | None = None) -> dict:
    g = abs(gain)
    if g == 0 or rin_ohm <= 0:
        raise ToolInputError("Gain and input resistance must be non-zero.")
    rf = g * rin_ohm
    rf_std = standard_value(rf, E24, "nearest")
    actual = rf_std / rin_ohm
    rows = [
        ("Rf needed (|G|·Rin)", rf, "Ω"),
        ("Rf, nearest E24", rf_std, "Ω"),
        ("Actual gain", f"−{actual:.4g}", "V/V"),
        ("Actual gain in dB", 20 * math.log10(actual), "dB"),
        ("Input impedance (= Rin)", rin_ohm, "Ω"),
    ]
    if gbw_hz:
        rows.append(("Closed-loop bandwidth ≈ GBW/(1+|G|)", gbw_hz / (1 + actual), "Hz"))
    warnings = []
    if rf_std > 1e6:
        warnings.append("Rf above 1 MΩ: noise and bias-current errors grow. Scale both resistors down.")
    if rin_ohm < 1000:
        warnings.append("Rin below 1 kΩ loads the signal source heavily.")
    parts = [
        _part("U1", "Op-amp", "Any general-purpose op-amp; choose GBW ≥ 10 × gain × highest signal frequency"),
        _part("R1", _si(rin_ohm, "Ω"), "Input resistor Rin; sets the input impedance"),
        _part("R2", _si(rf_std, "Ω"), "Feedback resistor Rf; gain = −R2/R1"),
    ]
    schematic = circuits.opamp_inverting(_si(rin_ohm, "Ω"), _si(rf_std, "Ω"), f"−{actual:.3g}")
    return result(
        f"Rf = {_si(rf_std, 'Ω')} with Rin = {_si(rin_ohm, 'Ω')} → gain −{actual:.3g}",
        rows,
        warnings=warnings,
        notes=[
            "Drawn for a split (±) supply with the + input grounded. On a single supply, bias the + input at mid-supply and AC-couple the input.",
            "The output cannot swing beyond the op-amp's supply rails; use a rail-to-rail part if you need the full range.",
        ],
        parts=parts,
        schematic=schematic,
    )


def opamp_noninverting(gain: float, rg_ohm: float = 10000, gbw_hz: float | None = None) -> dict:
    if gain <= 1:
        raise ToolInputError("Gain must be above 1. For a gain of exactly 1, wire the output straight to the − input (voltage follower).")
    if rg_ohm <= 0:
        raise ToolInputError("Rg must be positive.")
    rf = (gain - 1) * rg_ohm
    rf_std = standard_value(rf, E24, "nearest")
    actual = 1 + rf_std / rg_ohm
    rows = [
        ("Rf needed ((G−1)·Rg)", rf, "Ω"),
        ("Rf, nearest E24", rf_std, "Ω"),
        ("Actual gain", actual, "V/V"),
        ("Actual gain in dB", 20 * math.log10(actual), "dB"),
        ("Input impedance", "very high (op-amp input)", ""),
    ]
    if gbw_hz:
        rows.append(("Closed-loop bandwidth ≈ GBW/G", gbw_hz / actual, "Hz"))
    warnings = ["Rf above 1 MΩ: noise and bias-current errors grow. Scale both resistors down."] if rf_std > 1e6 else []
    parts = [
        _part("U1", "Op-amp", "Any general-purpose op-amp; choose GBW ≥ 10 × gain × highest signal frequency"),
        _part("R1", _si(rg_ohm, "Ω"), "Gain resistor Rg, from the − input to ground"),
        _part("R2", _si(rf_std, "Ω"), "Feedback resistor Rf; gain = 1 + R2/R1"),
    ]
    schematic = circuits.opamp_noninverting(_si(rg_ohm, "Ω"), _si(rf_std, "Ω"), f"{actual:.3g}")
    return result(
        f"Rf = {_si(rf_std, 'Ω')} with Rg = {_si(rg_ohm, 'Ω')} → gain {actual:.3g}",
        rows,
        warnings=warnings,
        notes=["Keep the input within the op-amp's common-mode range, and the output (G × Vin) within its output swing."],
        parts=parts,
        schematic=schematic,
    )


_LOAD_TYPES = ["resistive (lamp, LED strip, heater)", "inductive (relay, motor, solenoid)"]


def transistor_switch(supply_v: float, load_current_ma: float, logic_v: float = 3.3, hfe_min: float = 100, load: str = _LOAD_TYPES[0]) -> dict:
    vbe, vce_sat, r_off = 0.7, 0.2, 10_000.0
    if logic_v <= 1.2:
        raise ToolInputError("The logic (GPIO) voltage must be above about 1.2 V to switch an NPN transistor.")
    if supply_v <= vce_sat or load_current_ma <= 0 or hfe_min <= 0:
        raise ToolInputError("Supply voltage, load current and hFE must be positive.")
    ic = load_current_ma / 1000
    forced_beta = min(20.0, hfe_min / 3)  # drive well into saturation
    ib = ic / forced_beta
    rb = (logic_v - vbe) / (ib + vbe / r_off)
    rb_std = standard_value(rb, E12, "down")
    pin_ma = (logic_v - vbe) / rb_std * 1000
    ib_actual = pin_ma / 1000 - vbe / r_off
    inductive = load == _LOAD_TYPES[1]
    diode = "1N4148" if ic <= 0.15 else "1N4007"
    rows = [
        ("Collector (load) current", load_current_ma, "mA"),
        ("Minimum base current (Ic/hFE)", ic / hfe_min * 1000, "mA"),
        ("Design base current", ib_actual * 1000, "mA"),
        ("R1 needed", rb, "Ω"),
        ("R1, next E12 down", rb_std, "Ω"),
        ("GPIO pin current", pin_ma, "mA"),
        ("R2 (base pull-down)", r_off, "Ω"),
        ("Q1 dissipation (Vce(sat) ≈ 0.2 V)", vce_sat * ic * 1000, "mW"),
    ]
    warnings = []
    if pin_ma > 20:
        warnings.append(f"The GPIO pin must supply {pin_ma:.0f} mA, more than most microcontroller pins allow. Use a logic-level N-MOSFET or a Darlington.")
    if ic > 0.5:
        warnings.append("Above about 500 mA a logic-level N-MOSFET switches more efficiently than a small NPN.")
    if supply_v > 40:
        warnings.append("Check that Q1's Vceo rating exceeds the supply voltage with margin.")
    if ic <= 0.05:
        q_desc = "NPN, e.g. BC547 or 2N3904; Vceo above the supply"
    elif ic <= 0.3:
        q_desc = "NPN, e.g. 2N2222A or BC337; Vceo above the supply"
    else:
        q_desc = f"NPN rated well above {load_current_ma:g} mA, or a logic-level N-MOSFET"
    load_label = f"{load_current_ma:g} mA"
    parts = [
        _part("R1", _si(rb_std, "Ω"), "Base resistor; limits the GPIO current"),
        _part("R2", _si(r_off, "Ω"), "Holds Q1 off while the GPIO pin floats during reset"),
        _part("Q1", "NPN transistor", q_desc),
        _part("K1" if inductive else "Load", f"{_si(supply_v, 'V')}, {load_label}", "Relay coil or motor" if inductive else "The switched load"),
    ]
    notes = ["Ground of the load supply and the microcontroller must be connected."]
    if inductive:
        parts.append(_part("D1", diode, "Flyback diode across the coil, cathode to +V; clamps the turn-off spike"))
        notes.append("For PWM-driven motors use a fast or Schottky flyback diode (e.g. 1N5819) instead.")
    schematic = circuits.transistor_switch(_si(supply_v, "V"), load_label, _si(rb_std, "Ω"), _si(r_off, "Ω"), _si(logic_v, "V"), inductive, diode)
    return result(
        f"R1 = {_si(rb_std, 'Ω')} drives {load_current_ma:g} mA from a {logic_v:g} V pin ({pin_ma:.1f} mA from the pin)",
        rows,
        warnings=warnings,
        notes=notes,
        parts=parts,
        schematic=schematic,
    )


def linear_regulator(vin_v: float, vout_v: float, load_current_ma: float, dropout_v: float = 0.5,
                     theta_ja: float = 90, ambient_c: float = 25) -> dict:
    if vout_v <= 0 or vin_v <= 0 or load_current_ma <= 0:
        raise ToolInputError("Voltages and load current must be positive.")
    if vout_v >= vin_v:
        raise ToolInputError("A linear regulator only steps down: Vout must be below Vin. Use a boost converter to step up.")
    i = load_current_ma / 1000
    headroom = vin_v - vout_v
    p = headroom * i
    tj = ambient_c + p * theta_ja
    rows = [
        ("Headroom (Vin − Vout)", headroom, "V"),
        ("Margin above dropout", headroom - dropout_v, "V"),
        ("Power dissipated in U1", p, "W"),
        ("Efficiency (Vout/Vin)", 100 * vout_v / vin_v, "%"),
        ("Junction temperature estimate", tj, "°C"),
    ]
    warnings = []
    if headroom < dropout_v:
        warnings.append("Vin − Vout is below the dropout voltage: the output will sag. Pick a lower-dropout regulator or raise Vin.")
    elif headroom - dropout_v < 0.2:
        warnings.append("Less than 0.2 V above dropout: input ripple or a sagging battery will reach the output.")
    if tj > 125:
        warnings.append("The junction would exceed 125 °C. Use a larger package with copper area, share the load, or switch to a buck converter.")
    elif tj > 100:
        warnings.append("The regulator runs hot. Add copper area under its tab and check the datasheet's thermal limits.")
    if p > 1:
        warnings.append(f"{p:.1f} W is lost as heat; a buck converter would waste far less.")
    parts = [
        _part("U1", f"LDO, fixed {vout_v:g} V", f"Rated ≥ {1.5 * load_current_ma:.0f} mA, dropout ≤ {headroom:.2g} V at full load"),
        _part("C1", "10 µF", "Input capacitor, close to U1's input pin"),
        _part("C2", "10 µF", "Output capacitor; value and ESR as the regulator's datasheet requires"),
    ]
    schematic = circuits.linear_regulator(_si(vin_v, "V"), _si(vout_v, "V"), "10 µF", "10 µF", f"LDO {vout_v:g} V", f"{load_current_ma:g} mA")
    return result(
        f"{p:.2f} W dissipated, ≈{tj:.0f} °C junction, {100 * vout_v / vin_v:.0f}% efficient",
        rows,
        warnings=warnings,
        notes=["Junction estimate = ambient + P·θJA; θJA depends on the package and PCB copper — take it from the datasheet."],
        parts=parts,
        schematic=schematic,
    )


def button_pullup(vcc_v: float = 3.3, r_pullup_ohm: float = 10000, debounce_ms: float | None = None) -> dict:
    if vcc_v <= 0 or r_pullup_ohm <= 0:
        raise ToolInputError("Supply voltage and resistance must be positive.")
    i_pressed = vcc_v / r_pullup_ohm
    rows = [
        ("Current while pressed", i_pressed * 1000, "mA"),
        ("R1 dissipation while pressed", vcc_v * i_pressed * 1000, "mW"),
    ]
    cap = None
    if debounce_ms:
        c = debounce_ms / 1000 / (-math.log(0.3) * r_pullup_ohm)  # time for Vcc(1 − e^(−t/RC)) to reach 0.7·Vcc
        cap = standard_value(c, E6, "nearest")
        rows += [("C1 needed", c * 1e9, "nF"), ("C1, nearest E6", cap * 1e9, "nF"), ("Release delay to 0.7·Vcc", -math.log(0.3) * r_pullup_ohm * cap * 1000, "ms")]
    warnings = []
    if r_pullup_ohm < 1000:
        warnings.append("A pull-up below 1 kΩ wastes current while the button is held.")
    if r_pullup_ohm > 100_000:
        warnings.append("A pull-up above 100 kΩ is weak and picks up noise on long wires.")
    parts = [
        _part("R1", _si(r_pullup_ohm, "Ω"), "Pull-up resistor; holds the input HIGH"),
        _part("S1", "Push-button, normally open", "Pulls the input LOW when pressed"),
    ]
    if cap:
        parts.append(_part("C1", _si(cap, "F"), "Debounce capacitor; with R1 it filters contact bounce"))
    schematic = circuits.button_pullup(_si(vcc_v, "V"), _si(r_pullup_ohm, "Ω"), _si(cap, "F") if cap else None)
    return result(
        f"Pressed = LOW, {i_pressed * 1000:.2g} mA while held" + (f"; C1 = {_si(cap, 'F')} for ≈{debounce_ms:g} ms debounce" if cap else ""),
        rows,
        warnings=warnings,
        notes=[
            "Many microcontrollers have internal pull-ups (typically 20–50 kΩ) that can replace R1.",
            "An RC debounce gives a slow edge; read it with a Schmitt-trigger input, or debounce in software instead.",
        ],
        parts=parts,
        schematic=schematic,
    )


# ------------------------------------------------------------------ biomedical
def battery_life(capacity_mah: float, active_current_ma: float, sleep_current_ua: float, duty_cycle_pct: float, derating_pct: float = 20) -> dict:
    if capacity_mah <= 0:
        raise ToolInputError("Capacity must be positive.")
    duty = duty_cycle_pct / 100
    avg_ma = active_current_ma * duty + (sleep_current_ua / 1000) * (1 - duty)
    if avg_ma <= 0:
        raise ToolInputError("Average current must be positive.")
    usable = capacity_mah * (1 - derating_pct / 100)
    hours = usable / avg_ma
    return result(
        f"≈ {hours:.1f} h ({hours / 24:.1f} days) at {avg_ma:.3f} mA average",
        [
            ("Average current", avg_ma, "mA"),
            ("Usable capacity", usable, "mAh"),
            ("Estimated runtime", hours, "h"),
            ("Estimated runtime", hours / 24, "days"),
        ],
        notes=["Real runtime also depends on temperature, battery age, radio bursts and regulator efficiency."],
    )


def biosignal_sampling(max_signal_hz: float, oversampling: float, channels: float, adc_bits: float) -> dict:
    if max_signal_hz <= 0 or oversampling < 2:
        raise ToolInputError("Signal bandwidth must be positive and oversampling ≥ 2 (Nyquist).")
    nyquist = 2 * max_signal_hz
    fs = max_signal_hz * oversampling
    bytes_per_sample = math.ceil(adc_bits / 8)
    rate = fs * channels * bytes_per_sample
    per_day = rate * 86400
    return result(
        f"Sample at ≥ {fs:g} Hz → {rate / 1000:.2f} kB/s raw",
        [
            ("Nyquist minimum", nyquist, "Hz"),
            ("Recommended sampling rate", fs, "Hz"),
            ("Anti-aliasing filter cutoff (≤ fs/2)", fs / 2, "Hz"),
            ("Raw data rate", rate / 1000, "kB/s"),
            ("Storage per 24 h (uncompressed)", per_day / 1e6, "MB"),
        ],
    )


def adc_resolution(bits: float, vref_v: float, gain: float = 1) -> dict:
    if bits < 1 or vref_v <= 0 or gain <= 0:
        raise ToolInputError("Bits, Vref and gain must be positive.")
    levels = 2 ** int(bits)
    lsb = vref_v / levels
    return result(
        f"LSB = {_si(lsb, 'V')} at ADC, {_si(lsb / gain, 'V')} referred to input",
        [
            ("Quantisation levels", levels, ""),
            ("LSB at ADC input", lsb * 1e6, "µV"),
            ("LSB referred to sensor (÷ gain)", lsb / gain * 1e6, "µV"),
            ("Ideal SNR (6.02·N + 1.76)", 6.02 * int(bits) + 1.76, "dB"),
            ("Input range referred to sensor", vref_v / gain * 1000, "mV"),
        ],
    )


# ------------------------------------------------------------------ mechanical
def beam_point_load(support: str, load_n: float, length_m: float, youngs_gpa: float, width_mm: float, height_mm: float, yield_mpa: float | None = None) -> dict:
    if min(load_n, length_m, youngs_gpa, width_mm, height_mm) <= 0:
        raise ToolInputError("All inputs must be positive.")
    b, h = width_mm / 1000, height_mm / 1000
    inertia = b * h**3 / 12
    e = youngs_gpa * 1e9
    if support == "cantilever (end load)":
        deflection = load_n * length_m**3 / (3 * e * inertia)
        moment = load_n * length_m
        formula = "δ = FL³/3EI, M = FL"
    else:
        deflection = load_n * length_m**3 / (48 * e * inertia)
        moment = load_n * length_m / 4
        formula = "δ = FL³/48EI, M = FL/4"
    stress = moment * (h / 2) / inertia
    rows = [
        ("Second moment of area I (bh³/12)", inertia * 1e12, "mm⁴"),
        ("Max bending moment", moment, "N·m"),
        ("Max deflection", deflection * 1000, "mm"),
        ("Max bending stress", stress / 1e6, "MPa"),
    ]
    if yield_mpa:
        rows.append(("Factor of safety vs yield", yield_mpa / (stress / 1e6), ""))
    return result(f"δmax = {deflection * 1000:.3g} mm, σmax = {stress / 1e6:.3g} MPa ({formula})", rows)


def axial_stress(force_n: float, area_mm2: float, yield_mpa: float) -> dict:
    if area_mm2 <= 0:
        raise ToolInputError("Area must be positive.")
    stress = force_n / area_mm2  # N/mm² == MPa
    fos = yield_mpa / abs(stress) if stress else float("inf")
    warnings = ["Factor of safety below 1.5 — review design."] if fos < 1.5 else []
    return result(
        f"σ = {stress:.3g} MPa, FoS = {fos:.2f}",
        [("Axial stress", stress, "MPa"), ("Factor of safety vs yield", fos, "")],
        warnings=warnings,
    )


# ----------------------------------------------------------------------- civil
def udl_beam(load_kn_per_m: float, span_m: float, youngs_gpa: float, width_mm: float, depth_mm: float) -> dict:
    if min(load_kn_per_m, span_m, youngs_gpa, width_mm, depth_mm) <= 0:
        raise ToolInputError("All inputs must be positive.")
    w = load_kn_per_m * 1000
    inertia = (width_mm / 1000) * (depth_mm / 1000) ** 3 / 12
    e = youngs_gpa * 1e9
    moment = w * span_m**2 / 8
    shear = w * span_m / 2
    deflection = 5 * w * span_m**4 / (384 * e * inertia)
    limit = span_m / 250
    warnings = []
    if deflection > limit:
        warnings.append("Deflection exceeds span/250 — a common serviceability limit (e.g. IS 456). Increase depth or stiffness.")
    return result(
        f"Mmax = {moment / 1000:.2f} kN·m, Vmax = {shear / 1000:.2f} kN, δ = {deflection * 1000:.2f} mm",
        [
            ("Support reactions (each)", shear / 1000, "kN"),
            ("Max bending moment wL²/8", moment / 1000, "kN·m"),
            ("Max shear wL/2", shear / 1000, "kN"),
            ("Mid-span deflection 5wL⁴/384EI", deflection * 1000, "mm"),
            ("Span/250 limit", limit * 1000, "mm"),
        ],
        warnings=warnings,
        notes=["Gross uncracked section assumed; reinforced concrete design must follow the applicable code with a qualified engineer."],
    )


# ------------------------------------------------------------------ electrical
def three_phase_power(line_voltage_v: float, line_current_a: float, power_factor: float) -> dict:
    if not 0 < power_factor <= 1:
        raise ToolInputError("Power factor must be between 0 and 1.")
    s = math.sqrt(3) * line_voltage_v * line_current_a
    p = s * power_factor
    q = s * math.sin(math.acos(power_factor))
    return result(
        f"P = {p / 1000:.2f} kW, S = {s / 1000:.2f} kVA, Q = {q / 1000:.2f} kVAR",
        [("Real power P = √3·V·I·PF", p / 1000, "kW"), ("Apparent power S", s / 1000, "kVA"), ("Reactive power Q", q / 1000, "kVAR")],
    )


_RESISTIVITY = {"copper": 1.724e-8, "aluminium": 2.82e-8}


def voltage_drop(system: str, supply_v: float, current_a: float, length_m: float, area_mm2: float, conductor: str) -> dict:
    if min(supply_v, current_a, length_m, area_mm2) <= 0:
        raise ToolInputError("All inputs must be positive.")
    rho = _RESISTIVITY[conductor]
    r_per_m = rho / (area_mm2 * 1e-6)
    if system == "three-phase":
        drop = math.sqrt(3) * current_a * r_per_m * length_m
    else:
        drop = 2 * current_a * r_per_m * length_m  # out and return conductors
    pct = 100 * drop / supply_v
    warnings = ["Drop above 5% — consider a larger conductor."] if pct > 5 else []
    return result(
        f"ΔV = {drop:.2f} V ({pct:.2f}%)",
        [
            ("Conductor resistance", r_per_m * 1000, "Ω/km"),
            ("Voltage drop", drop, "V"),
            ("Voltage drop", pct, "%"),
            ("Voltage at load", supply_v - drop, "V"),
        ],
        warnings=warnings,
        notes=["Resistive drop at 20 °C; ignores reactance and temperature rise. Check ampacity separately."],
    )


TOOLS = [
    ToolSpec("ohms_law", "Ohm's law", "Solve V = I·R for the missing value and power.", "hardware", ohms_law,
             [Param("voltage_v", "Voltage", unit="V", required=False), Param("current_a", "Current", unit="A", required=False),
              Param("resistance_ohm", "Resistance", unit="Ω", required=False)],
             plugin="electronics", category="Circuits", formula="V = I·R, P = V·I"),
    ToolSpec("voltage_divider", "Voltage divider", "Output voltage of a resistive divider, with optional load.", "hardware", voltage_divider,
             [Param("vin_v", "Input voltage", unit="V", default=5), Param("r1_ohm", "R1 (top)", unit="Ω", default=10000),
              Param("r2_ohm", "R2 (bottom)", unit="Ω", default=10000, overridden_by="target_vout_v"),
              Param("target_vout_v", "Target Vout", unit="V", required=False, help="optional; picks R2 from R1"),
              Param("load_ohm", "Load resistance", unit="Ω", required=False)],
             plugin="electronics", category="Circuits", formula="Vout = Vin·R2/(R1+R2)", schematic=True),
    ToolSpec("led_resistor", "LED series resistor", "Current-limiting resistor with the next E12 value.", "hardware", led_resistor,
             [Param("supply_v", "Supply voltage", unit="V", default=3.3), Param("forward_v", "LED forward voltage", unit="V", default=2.0,
                                                                              help="Red ≈ 2 V, green/blue/white ≈ 3 V"),
              Param("current_ma", "LED current", unit="mA", default=10)],
             plugin="electronics", category="Circuits", formula="R = (Vs − Vf)/I", schematic=True),
    ToolSpec("button_pullup", "Push-button with pull-up", "Input wiring for a button on a microcontroller pin, with optional RC debounce.", "hardware", button_pullup,
             [Param("vcc_v", "Logic supply", unit="V", default=3.3), Param("r_pullup_ohm", "Pull-up resistor", unit="Ω", default=10000),
              Param("debounce_ms", "Debounce time", unit="ms", required=False, help="optional, e.g. 5")],
             plugin="electronics", category="Circuits", formula="t = −RC·ln(0.3) ≈ 1.2RC", schematic=True),
    ToolSpec("transistor_switch", "NPN transistor switch", "Base resistor for switching a load from a microcontroller pin.", "hardware", transistor_switch,
             [Param("supply_v", "Load supply", unit="V", default=12), Param("load_current_ma", "Load current", unit="mA", default=100),
              Param("logic_v", "GPIO voltage", unit="V", default=3.3), Param("hfe_min", "Minimum hFE", default=100, help="From the datasheet at your current"),
              Param("load", "Load type", type="select", default=_LOAD_TYPES[0], options=_LOAD_TYPES)],
             plugin="electronics", category="Circuits", formula="Rb = (Vgpio − Vbe)/Ib, Ib = Ic/βforced", schematic=True),
    ToolSpec("rc_filter", "RC low/high-pass filter", "Cutoff frequency and time constant of a first-order RC network.", "hardware", rc_filter,
             [Param("kind", "Type", type="select", default="low-pass", options=["low-pass", "high-pass"]),
              Param("resistance_ohm", "Resistance", unit="Ω", default=10000), Param("capacitance_f", "Capacitance", unit="F", default=1e-7, overridden_by="cutoff_hz"),
              Param("cutoff_hz", "Target cutoff", unit="Hz", required=False, help="optional; picks C from R")],
             plugin="electronics", category="Filters", formula="fc = 1/(2πRC)", schematic=True),
    ToolSpec("opamp_inverting", "Inverting op-amp amplifier", "Feedback resistor and bandwidth for an inverting amplifier.", "hardware", opamp_inverting,
             [Param("gain", "Gain magnitude |G|", unit="V/V", default=10), Param("rin_ohm", "Input resistor Rin", unit="Ω", default=10000),
              Param("gbw_hz", "Op-amp gain-bandwidth", unit="Hz", required=False, help="optional, from the datasheet, e.g. 1M")],
             plugin="electronics", category="Amplifiers", formula="G = −Rf/Rin", schematic=True),
    ToolSpec("opamp_noninverting", "Non-inverting op-amp amplifier", "Feedback resistor and bandwidth for a non-inverting amplifier.", "hardware", opamp_noninverting,
             [Param("gain", "Gain", unit="V/V", default=11), Param("rg_ohm", "Gain resistor Rg", unit="Ω", default=10000),
              Param("gbw_hz", "Op-amp gain-bandwidth", unit="Hz", required=False, help="optional, from the datasheet, e.g. 1M")],
             plugin="electronics", category="Amplifiers", formula="G = 1 + Rf/Rg", schematic=True),
    ToolSpec("linear_regulator", "Linear regulator (LDO)", "Dissipation, efficiency and temperature of a linear regulator.", "hardware", linear_regulator,
             [Param("vin_v", "Input voltage", unit="V", default=5), Param("vout_v", "Output voltage", unit="V", default=3.3),
              Param("load_current_ma", "Load current", unit="mA", default=250),
              Param("dropout_v", "Dropout voltage", unit="V", default=0.5, help="From the datasheet at your load current"),
              Param("theta_ja", "Thermal resistance θJA", unit="°C/W", default=90, help="SOT-223 ≈ 60–110, SOT-23 ≈ 180–250"),
              Param("ambient_c", "Ambient temperature", unit="°C", default=25)],
             plugin="electronics", category="Power", formula="P = (Vin − Vout)·I, Tj = Ta + P·θJA", schematic=True),
    ToolSpec("battery_life", "Wearable battery life", "Runtime from capacity, active/sleep current and duty cycle.", "hardware", battery_life,
             [Param("capacity_mah", "Battery capacity", unit="mAh", default=200), Param("active_current_ma", "Active current", unit="mA", default=8),
              Param("sleep_current_ua", "Sleep current", unit="µA", default=5), Param("duty_cycle_pct", "Active duty cycle", unit="%", default=10, min=0, max=100),
              Param("derating_pct", "Capacity derating", unit="%", default=20, min=0, max=90)],
             plugin="biomedical", category="Power", formula="t = C·(1−derating) / (Iact·D + Isleep·(1−D))"),
    ToolSpec("biosignal_sampling", "Biosignal sampling & data rate", "Sampling rate from signal bandwidth, plus raw data rate and storage.", "hardware", biosignal_sampling,
             [Param("max_signal_hz", "Highest signal frequency", unit="Hz", default=150, help="e.g. ECG diagnostic bandwidth ≈ 150 Hz"),
              Param("oversampling", "Oversampling factor", unit="× fmax", default=4, min=2), Param("channels", "Channels", default=1, min=1),
              Param("adc_bits", "ADC resolution", unit="bits", default=24, min=1, max=32)],
             plugin="biomedical", category="Signal acquisition", formula="fs ≥ 2·fmax (Nyquist)"),
    ToolSpec("adc_resolution", "ADC resolution", "LSB size and ideal SNR for an ADC with front-end gain.", "hardware", adc_resolution,
             [Param("bits", "ADC bits", unit="bits", default=24, min=1, max=32), Param("vref_v", "Reference voltage", unit="V", default=2.4),
              Param("gain", "Front-end gain", unit="V/V", default=6)],
             plugin="biomedical", category="Signal acquisition", formula="LSB = Vref/2ᴺ, SNR = 6.02N + 1.76 dB"),
    ToolSpec("beam_point_load", "Beam with point load", "Deflection and bending stress of a rectangular beam.", "hardware", beam_point_load,
             [Param("support", "Support", type="select", default="simply supported (centre load)",
                    options=["simply supported (centre load)", "cantilever (end load)"]),
              Param("load_n", "Load", unit="N", default=500), Param("length_m", "Length", unit="m", default=1),
              Param("youngs_gpa", "Young's modulus", unit="GPa", default=200, help="Steel ≈ 200, Al 6061 ≈ 69"),
              Param("width_mm", "Section width b", unit="mm", default=20), Param("height_mm", "Section height h", unit="mm", default=40),
              Param("yield_mpa", "Yield strength", unit="MPa", required=False)],
             plugin="mechanical", category="Structures", formula="I = bh³/12, σ = Mc/I"),
    ToolSpec("axial_stress", "Axial stress & factor of safety", "Normal stress in a member and safety factor against yield.", "hardware", axial_stress,
             [Param("force_n", "Axial force", unit="N", default=10000), Param("area_mm2", "Cross-section area", unit="mm²", default=100),
              Param("yield_mpa", "Yield strength", unit="MPa", default=250)],
             plugin="mechanical", category="Strength", formula="σ = F/A, FoS = σy/σ"),
    ToolSpec("udl_beam", "Simply supported beam (UDL)", "Reactions, moment, shear and deflection under uniform load.", "hardware", udl_beam,
             [Param("load_kn_per_m", "Uniform load w", unit="kN/m", default=10), Param("span_m", "Span", unit="m", default=5),
              Param("youngs_gpa", "Young's modulus", unit="GPa", default=25, help="Concrete M25 ≈ 25 GPa (5000√fck MPa per IS 456)"),
              Param("width_mm", "Width b", unit="mm", default=230), Param("depth_mm", "Depth D", unit="mm", default=450)],
             plugin="civil", category="Structures", formula="M = wL²/8, δ = 5wL⁴/384EI"),
    ToolSpec("three_phase_power", "Three-phase power", "Real, apparent and reactive power of a balanced three-phase load.", "hardware", three_phase_power,
             [Param("line_voltage_v", "Line voltage", unit="V", default=415), Param("line_current_a", "Line current", unit="A", default=20),
              Param("power_factor", "Power factor", default=0.85, min=0.01, max=1)],
             plugin="electrical", category="Power", formula="P = √3·VL·IL·PF"),
    ToolSpec("voltage_drop", "Cable voltage drop", "Resistive voltage drop for single- or three-phase runs.", "hardware", voltage_drop,
             [Param("system", "System", type="select", default="single-phase", options=["single-phase", "three-phase"]),
              Param("supply_v", "Supply voltage", unit="V", default=230), Param("current_a", "Load current", unit="A", default=16),
              Param("length_m", "One-way length", unit="m", default=30), Param("area_mm2", "Conductor size", unit="mm²", default=2.5),
              Param("conductor", "Conductor", type="select", default="copper", options=["copper", "aluminium"])],
             plugin="electrical", category="Wiring", formula="ΔV = 2·I·ρL/A (1φ), √3·I·ρL/A (3φ)"),
]
