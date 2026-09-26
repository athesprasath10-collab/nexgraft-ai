import math

import pytest

from nexgraft.tools import TOOL_REGISTRY, ToolInputError
from nexgraft.tools.engineering import next_standard_resistor
from nexgraft.tools.sequence import (
    detect_type,
    find_orfs,
    find_sequences_in_text,
    parse_sequences,
    reverse_complement,
    translate,
)


def values(output):
    return {row["label"]: row["value"] for row in output["results"]}


def test_parse_fasta_and_raw():
    recs = parse_sequences(">a desc\nACGT\nAC\n>b\nGGG")
    assert recs == [("a desc", "ACGTAC"), ("b", "GGG")]
    assert parse_sequences("acgt 12 acgt") == [("sequence", "ACGTACGT")]


def test_detect_type():
    assert detect_type("ACGTACGTNN") == "DNA"
    assert detect_type("ACGUACGU") == "RNA"
    assert detect_type("MKTAYIAKQRQISFVKSHFSRQ") == "protein"


def test_reverse_complement_and_translation():
    assert reverse_complement("ATGCCG") == "CGGCAT"
    assert translate("ATGGCCTAA") == "MA*"
    assert translate("ATGGCCTAA", to_stop=True) == "MA"
    assert translate("AUGGCC") == "MA"


def test_orfs_both_strands():
    orfs = find_orfs("CCATGAAATTTGGGCCCTAAGG", min_aa=3)
    assert orfs[0]["protein"] == "MKFGP"
    assert orfs[0]["strand"] == "+"
    rc = reverse_complement("CCATGAAATTTGGGCCCTAAGG")
    assert find_orfs(rc, min_aa=3)[0]["strand"] == "-"


@pytest.mark.asyncio
async def test_sequence_stats_gc():
    out = await TOOL_REGISTRY["sequence_stats"].execute({"sequence": "GGCCAATT"})
    assert values(out)["GC content"] == 50.0
    assert values(out)["Length"] == 8


@pytest.mark.asyncio
async def test_protein_mass():
    out = await TOOL_REGISTRY["sequence_stats"].execute({"sequence": "GG"})  # treated as DNA
    assert values(out)["Type"] == "DNA"
    out = await TOOL_REGISTRY["sequence_stats"].execute({"sequence": "MKW"})
    # M + K + W residues + water
    expected = (131.1926 + 128.1741 + 186.2132 + 18.01528) / 1000
    assert math.isclose(values(out)["Molecular weight (average)"], round(expected, 4), rel_tol=1e-3)


def test_find_sequences_in_text():
    found = find_sequences_in_text("please check ATGCGTACGTTAGCTAGCTAGG for me")
    assert found and found[0][1].startswith("ATGCG")
    assert find_sequences_in_text("no sequence here") == []


@pytest.mark.asyncio
async def test_alignment():
    out = await TOOL_REGISTRY["pairwise_align"].execute({"sequence_a": "ACGTACGT", "sequence_b": "ACGTACGT"})
    assert values(out)["Identity"] == 100.0


def test_e12():
    assert next_standard_resistor(150) == 150
    assert next_standard_resistor(151) == 180
    assert next_standard_resistor(9.9) == 10


@pytest.mark.asyncio
async def test_led_resistor():
    out = await TOOL_REGISTRY["led_resistor"].execute({"supply_v": 5, "forward_v": 2, "current_ma": 20})
    assert values(out)["Next E12 value"] == 150.0


@pytest.mark.asyncio
async def test_beam_formulas():
    out = await TOOL_REGISTRY["beam_point_load"].execute(
        {"support": "cantilever (end load)", "load_n": 100, "length_m": 1, "youngs_gpa": 200, "width_mm": 10, "height_mm": 10}
    )
    inertia = 0.01 * 0.01**3 / 12
    expected_mm = 100 * 1**3 / (3 * 200e9 * inertia) * 1000
    assert math.isclose(values(out)["Max deflection"], round(expected_mm, 2), rel_tol=1e-3)


@pytest.mark.asyncio
async def test_udl_beam_and_voltage_drop():
    out = await TOOL_REGISTRY["udl_beam"].execute({"load_kn_per_m": 10, "span_m": 5, "youngs_gpa": 25, "width_mm": 230, "depth_mm": 450})
    assert values(out)["Max bending moment wL²/8"] == 31.25
    out = await TOOL_REGISTRY["voltage_drop"].execute({"system": "single-phase", "supply_v": 230, "current_a": 10, "length_m": 10, "area_mm2": 1.0, "conductor": "copper"})
    assert math.isclose(out["results"][1]["value"], 2 * 10 * 1.724e-8 / 1e-6 * 10, rel_tol=1e-3)


@pytest.mark.asyncio
async def test_input_validation():
    with pytest.raises(ToolInputError):
        await TOOL_REGISTRY["ohms_law"].execute({"voltage_v": 5})
    with pytest.raises(ToolInputError):
        await TOOL_REGISTRY["led_resistor"].execute({"supply_v": 1, "forward_v": 2, "current_ma": 10})
    with pytest.raises(ToolInputError):
        await TOOL_REGISTRY["battery_life"].execute({"capacity_mah": "abc"})


def test_parse_quantity_units_and_prefixes():
    from nexgraft.tools.base import parse_quantity as q

    assert q("10k", "Ω") == 10_000 and q("4k7", "Ω") == 4_700 and q("2.2 kohm", "Ω") == 2_200 and q("1M", "Ω") == 1e6
    assert math.isclose(q("100 nF", "F"), 1e-7) and math.isclose(q("0.1uF", "F"), 1e-7)
    assert q("20 mA", "mA") == 20 and math.isclose(q("0.02 A", "mA"), 20) and q("3V3", "V") == 3.3
    assert q("90", "°C/W") == 90 and q(5, "V") == 5
    for bad, unit in [("abc", "V"), ("5 V", "mA"), ("10 dB", "V/V")]:
        with pytest.raises(ValueError):
            q(bad, unit)


def test_standard_values():
    from nexgraft.tools.engineering import E6, E24, standard_value

    assert standard_value(638, mode="down") == 560
    assert standard_value(4.15e-7, E6, "nearest") == 4.7e-7
    assert standard_value(4.4e-12, E6, "nearest") == 4.7e-12
    assert standard_value(199_000, E24, "nearest") == 200_000


def _svg_ok(output):
    import xml.etree.ElementTree as ET

    root = ET.fromstring(output["schematic"]["svg"])
    assert root.tag.endswith("svg") and output["schematic"]["title"] and output["parts"]


@pytest.mark.asyncio
async def test_circuit_calculators_draw_schematics():
    t = TOOL_REGISTRY
    out = await t["opamp_inverting"].execute({"gain": "-20", "rin_ohm": "10k", "gbw_hz": "1M"})
    assert values(out)["Rf, nearest E24"] == 200_000 and values(out)["Closed-loop bandwidth ≈ GBW/(1+|G|)"] == round(1e6 / 21, 2)
    out = await t["opamp_noninverting"].execute({"gain": 11})
    assert values(out)["Actual gain"] == 11.0
    with pytest.raises(ToolInputError):
        await t["opamp_noninverting"].execute({"gain": 1})
    out = await t["transistor_switch"].execute({"supply_v": 12, "load_current_ma": 80, "load": "inductive"})
    assert values(out)["R1, next E12 down"] == 560 and any(p["ref"] == "D1" for p in out["parts"])
    assert not out.get("warnings")
    heavy = await t["transistor_switch"].execute({"supply_v": 12, "load_current_ma": 800})
    assert len(heavy["warnings"]) == 2
    out = await t["linear_regulator"].execute({"vin_v": 5, "vout_v": 3.3, "load_current_ma": 500, "dropout_v": 1.1})
    assert values(out)["Power dissipated in U1"] == 0.85 and out["warnings"]
    with pytest.raises(ToolInputError):
        await t["linear_regulator"].execute({"vin_v": 3.3, "vout_v": 5, "load_current_ma": 100})
    out = await t["button_pullup"].execute({"debounce_ms": 5})
    assert values(out)["C1, nearest E6"] == 470
    assert (await t["rc_filter"].execute({"kind": "high", "resistance_ohm": "10k", "capacitance_f": "100n"}))["summary"].startswith("high-pass")
    for tool in t.values():
        if tool.schematic:
            _svg_ok(await tool.execute({}))
    _svg_ok(await t["voltage_divider"].execute({"load_ohm": "100k"}))
    _svg_ok(await t["button_pullup"].execute({"debounce_ms": 10}))
    _svg_ok(await t["transistor_switch"].execute({"supply_v": 5, "load_current_ma": 30, "load": "inductive"}))


def test_quantities_in_text_keep_units():
    from nexgraft.tools.base import quantities_in_text

    found = quantities_in_text("ESP32 at 300 mA, 5V to 3V3, 4k7 pull-up, gain of 5, 1 kHz")
    assert (0.3, "A") in found and (5.0, "V") in found and (3.3, "V") in found and (4700.0, None) in found
    assert (5.0, None) in found and (1000.0, "Hz") in found
    assert all(q != 32 for q, _ in found)
