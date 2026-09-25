import pytest

from nexgraft.agents.registry import registry
from nexgraft.orchestrator.analyzer import apply_guard, normalise_llm_plan
from nexgraft.orchestrator.heuristics import heuristic_analysis


def agents(message):
    return [t["agent"] for t in heuristic_analysis(message, registry)["tasks"]]


@pytest.mark.parametrize(
    "message, expected",
    [
        ("Explain Newton's laws.", ["general"]),
        ("I have a college project idea. Help me create a development plan.", ["general"]),
        ("Generate a Python workflow for protein sequence analysis.", ["bioinformatics"]),
        ("Generate Python code to analyze a DNA sequence and calculate GC content.", ["bioinformatics"]),
        ("Explain recent research on diabetes biomarkers.", ["medical"]),
        ("Find and summarize research about wearable monitoring of cardiac parameters.", ["medical"]),
        ("What sensors and materials could be considered for a biomedical wearable?", ["hardware"]),
    ],
)
def test_single_workspace_routing(message, expected):
    assert agents(message) == expected


def test_multi_workspace_decomposition():
    msg = ("I want to develop a wearable biomedical system for monitoring physiological parameters "
           "and analyze the collected biological data.")
    result = heuristic_analysis(msg, registry)
    assert set(t["agent"] for t in result["tasks"]) == {"general", "medical", "hardware", "bioinformatics"}
    assert result["tasks"][0]["agent"] == "general"
    assert result["hardware_domain"] == "biomedical"


def test_design_plus_research_is_two_workspaces():
    msg = "Design a wearable biomedical device and explain the medical research supporting the selected measurements."
    assert set(agents(msg)) == {"hardware", "medical"}


def test_plugin_detection():
    assert heuristic_analysis("Check deflection of a 5 m RCC beam", registry)["hardware_domain"] == "civil"
    assert heuristic_analysis("Design an LED circuit on a PCB with a resistor", registry)["hardware_domain"] == "electronics"


def test_normalise_merges_duplicates_and_drops_unknown():
    raw = {
        "domain": "X", "intent": "Y", "capabilities": ["a"], "hardware_domain": "electronics",
        "tasks": [
            {"workspace": "hardware", "title": "A", "instruction": "one", "search_query": "q"},
            {"workspace": "hardware", "title": "B", "instruction": "two", "search_query": "q"},
            {"workspace": "unknown", "title": "C", "instruction": "x", "search_query": "q"},
        ],
    }
    plan = normalise_llm_plan(raw, "msg", registry)
    assert [t["agent"] for t in plan["tasks"]] == ["hardware"]
    assert plan["tasks"][0]["instruction"] == "one two"
    assert plan["hardware_domain"] == "electronics"
    assert normalise_llm_plan({"tasks": []}, "msg", registry) is None


def test_guard_rescues_general_only_plan():
    msg = "Generate Python code to analyze a DNA sequence and calculate GC content."
    heur = heuristic_analysis(msg, registry)
    plan = {"tasks": [{"agent": "general", "title": "t", "instruction": msg, "search_query": ""}]}
    notes = apply_guard(plan, heur, msg, "en")
    assert notes and plan["tasks"][0]["agent"] == "bioinformatics"


def test_guard_drops_unsupported_extra_workspaces():
    msg = "Explain Newton's laws."
    heur = heuristic_analysis(msg, registry)
    plan = {"tasks": [
        {"agent": "general", "title": "t", "instruction": msg, "search_query": ""},
        {"agent": "medical", "title": "m", "instruction": msg, "search_query": ""},
    ]}
    apply_guard(plan, heur, msg, "en")
    assert [t["agent"] for t in plan["tasks"]] == ["general"]


def test_guard_skipped_for_non_english():
    plan = {"tasks": [{"agent": "general", "title": "t", "instruction": "x", "search_query": ""}]}
    heur = heuristic_analysis("DNA sequence GC content fasta", registry)
    assert apply_guard(plan, heur, "x", "ta") == []
