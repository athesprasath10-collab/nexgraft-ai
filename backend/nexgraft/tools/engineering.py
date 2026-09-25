"""Engineering calculators used by Hardware Design AI domain plugins.

Every calculator uses a standard textbook formula shown in `formula`. They are
first-pass design aids; the user validates results against datasheets, codes
and their own analysis.
"""

from __future__ import annotations

import math

from .base import Param, ToolInputError, ToolSpec, result

E12 = [1.0, 1.2, 1.5, 1.8, 2.2, 2.7, 3.3, 3.9, 4.7, 5.6, 6.8, 8.2]


def next_standard_resistor(value: float, series: list[float] = E12) -> float:
    """Smallest standard value ≥ value."""
    if value <= 0:
        raise ToolInputError("Resistance must be positive.")
    decade = 10 ** math.floor(math.log10(value))
    for base in series + [10.0]:
        candidate = round(base * decade, 10)
        if candidate >= value * (1 - 1e-9):
            return candidate
    return 10 * decade


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


def voltage_divider(vin_v: float, r1_ohm: float, r2_ohm: float, load_ohm: float | None = None) -> dict:
    if r1_ohm <= 0 or r2_ohm <= 0:
        raise ToolInputError("Resistances must be positive.")
    r2_eff = r2_ohm if not load_ohm else (r2_ohm * load_ohm) / (r2_ohm + load_ohm)
    vout = vin_v * r2_eff / (r1_ohm + r2_eff)
    current = vin_v / (r1_ohm + r2_eff)
    rows = [
        ("Vout", vout, "V"),
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
    return result(f"Vout = {vout:.4g} V", rows, warnings=warnings)


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
    return result(
        f"Use {_si(r_std, 'Ω')} (E12) → {i_actual * 1000:.1f} mA",
        [
            ("Calculated resistance", r, "Ω"),
            ("Next E12 value", r_std, "Ω"),
            ("Actual LED current", i_actual * 1000, "mA"),
            ("Resistor dissipation", p * 1000, "mW"),
            ("Suggested power rating (2× margin)", f"{rating} W" if rating else "> 5 W — reconsider design", ""),
        ],
    )


def rc_filter(resistance_ohm: float, capacitance_f: float) -> dict:
    if resistance_ohm <= 0 or capacitance_f <= 0:
        raise ToolInputError("R and C must be positive.")
    tau = resistance_ohm * capacitance_f
    fc = 1 / (2 * math.pi * tau)
    return result(
        f"fc = {_si(fc, 'Hz')}, τ = {_si(tau, 's')}",
        [
            ("Cutoff frequency (−3 dB)", fc, "Hz"),
            ("Time constant τ", tau, "s"),
            ("Rise time 10–90% (≈2.2τ)", 2.2 * tau, "s"),
            ("Settling to 99% (≈4.6τ)", 4.6 * tau, "s"),
        ],
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
              Param("r2_ohm", "R2 (bottom)", unit="Ω", default=10000), Param("load_ohm", "Load resistance", unit="Ω", required=False)],
             plugin="electronics", category="Circuits", formula="Vout = Vin·R2/(R1+R2)"),
    ToolSpec("led_resistor", "LED series resistor", "Current-limiting resistor with the next E12 value.", "hardware", led_resistor,
             [Param("supply_v", "Supply voltage", unit="V", default=3.3), Param("forward_v", "LED forward voltage", unit="V", default=2.0),
              Param("current_ma", "LED current", unit="mA", default=10)],
             plugin="electronics", category="Circuits", formula="R = (Vs − Vf)/I"),
    ToolSpec("rc_filter", "RC low/high-pass filter", "Cutoff frequency and time constant of a first-order RC network.", "hardware", rc_filter,
             [Param("resistance_ohm", "Resistance", unit="Ω", default=10000), Param("capacitance_f", "Capacitance", unit="F", default=1e-7)],
             plugin="electronics", category="Filters", formula="fc = 1/(2πRC)"),
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
