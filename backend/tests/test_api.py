import json

from fastapi.testclient import TestClient

from nexgraft.main import app


def events(response):
    return [json.loads(line) for line in response.text.splitlines() if line.strip()]


def test_config_lists_workspaces_plugins_tools():
    with TestClient(app) as client:
        cfg = client.get("/api/config").json()
    assert [a["id"] for a in cfg["agents"]] == ["general", "bioinformatics", "medical", "hardware"]
    assert {p["id"] for p in cfg["plugins"]} >= {"biomedical", "electronics", "mechanical", "civil", "electrical"}
    assert any(t["id"] == "sequence_stats" for t in cfg["tools"])
    assert "hero_model" in cfg and "spline_scene" in cfg


def test_analyze_llm_path(fake_ollama):
    with TestClient(app) as client:
        r = client.post("/api/analyze", json={"message": "Explain Newton's laws."})
    ev = events(r)
    stages = [e["stage"] for e in ev if e["type"] == "stage" and e["status"] == "done"]
    assert stages == ["understand", "analyze", "decompose", "route"]
    analysis = next(e["analysis"] for e in ev if e["type"] == "analysis")
    assert analysis["router"] == "llm"
    assert [t["agent"] for t in analysis["tasks"]] == ["general"]
    assert ev[-1]["type"] == "done"


def test_analyze_heuristic_mode(fake_ollama):
    with TestClient(app) as client:
        r = client.post("/api/analyze", json={"message": "Explain recent research on diabetes biomarkers.", "options": {"router": "heuristic"}})
    analysis = next(e["analysis"] for e in events(r) if e["type"] == "analysis")
    assert analysis["router"] == "heuristic"
    assert analysis["tasks"][0]["agent"] == "medical"
    assert not fake_ollama["json"]


def test_run_streams_tokens_and_tool_results(fake_ollama):
    with TestClient(app) as client:
        r = client.post("/api/run", json={"message": "GC content of ATGCGCGCATATATGCGCGCAT please", "agent": "bioinformatics"})
    ev = events(r)
    types = [e["type"] for e in ev]
    assert types[0] == "run_start" and types[-1] == "done"
    assert any(e["type"] == "tool" and e["tool"] == "sequence_stats" for e in ev)
    text = "".join(e["content"] for e in ev if e["type"] == "token")
    assert text == "Hello from NEXGRAFT"
    prompt = fake_ollama["chat"][0][-1]["content"]
    assert "Verified tool results" in prompt and "GC" in prompt


def test_multi_task_run_synthesises(fake_ollama):
    tasks = [
        {"id": "a", "agent": "medical", "title": "Research", "instruction": "research part"},
        {"id": "b", "agent": "hardware", "title": "Hardware", "instruction": "hardware part", "plugin": "biomedical"},
    ]
    with TestClient(app) as client:
        r = client.post("/api/run", json={"message": "wearable", "tasks": tasks, "options": {"literature": False}})
    ev = events(r)
    ends = [e["task_id"] for e in ev if e["type"] == "task_end"]
    assert ends == ["t1", "t2", "synthesis"]
    system_prompt = fake_ollama["chat"][1][0]["content"]
    assert "Biomedical Engineering" in system_prompt


def test_run_rejects_unknown_workspace(fake_ollama):
    with TestClient(app) as client:
        r = client.post("/api/run", json={"message": "x", "agent": "astrology"})
    assert r.status_code == 400


def test_tools_endpoint():
    with TestClient(app) as client:
        ok = client.post("/api/tools/ohms_law", json={"params": {"voltage_v": 5, "resistance_ohm": 1000}})
        bad = client.post("/api/tools/ohms_law", json={"params": {}})
    assert ok.status_code == 200 and ok.json()["output"]["results"][1]["value"] == 0.005
    assert bad.status_code == 400


def test_security_middleware():
    with TestClient(app) as client:
        assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
        r = client.post("/api/tools/ohms_law", json={"params": {}}, headers={"origin": "https://evil.example"})
        assert r.status_code == 403


def test_upload_document_and_run_code(fake_ollama):
    with TestClient(app) as client:
        up = client.post("/api/attachments", files={"file": ("reads.fasta", b">r1\nACGT\n", "text/plain")})
        assert up.status_code == 200
        att = up.json()
        assert att["kind"] == "document" and att["name"] == "reads.fasta"
        code = "print(open('reads.fasta').read().splitlines()[1])"
        res = client.post("/api/execute", json={"code": code, "attachments": [att["id"]]}).json()
    assert res["exit_code"] == 0 and res["stdout"].strip() == "ACGT"


def test_image_without_vision_model(fake_ollama):
    with TestClient(app) as client:
        r = client.post("/api/attachments", files={"file": ("photo.png", b"\x89PNG....", "image/png")})
    assert r.status_code == 422
    assert "vision model" in r.json()["detail"]


def _generating_model(agent, options=None):
    with TestClient(app) as client:
        r = client.post("/api/run", json={"message": "reverse complement of ATGC", "agent": agent, "options": options or {}})
    return next(e["model"] for e in events(r) if e["type"] == "task_phase" and e["phase"] == "generating")


def test_workspace_uses_its_finetuned_model(fake_ollama, monkeypatch):
    from nexgraft.config import settings
    from nexgraft.llm.ollama import ModelInfo, ollama

    async def list_models(refresh=False):
        return [ModelInfo(name="qwen2.5:3b", capabilities=["completion"]), ModelInfo(name="nexgraft-bioinformatics:latest", capabilities=["completion"])]

    monkeypatch.setattr(ollama, "list_models", list_models)
    assert _generating_model("bioinformatics") == "nexgraft-bioinformatics:latest"
    assert _generating_model("general") == "qwen2.5:3b"
    assert _generating_model("bioinformatics", {"agent_models": {"bioinformatics": "qwen2.5:3b"}}) == "qwen2.5:3b"
    monkeypatch.setattr(settings, "use_finetuned", False)
    assert _generating_model("bioinformatics") == "qwen2.5:3b"


def test_finetuned_models_are_not_the_general_default():
    from nexgraft.llm.ollama import ModelInfo, OllamaClient

    models = [ModelInfo(name="nexgraft-hardware:latest", size=1), ModelInfo(name="llama3.2:3b", size=2)]
    assert OllamaClient.pick_default(models) == "llama3.2:3b"


def test_analyzer_timeout_falls_back_to_keyword_router(fake_ollama, monkeypatch):
    from nexgraft.llm.ollama import OllamaError, ollama

    async def slow_json(*args, **kwargs):
        raise OllamaError("the model took longer than 60 s")

    monkeypatch.setattr(ollama, "chat_json", slow_json)
    with TestClient(app) as client:
        r = client.post("/api/analyze", json={"message": "Explain recent research on diabetes biomarkers."})
    analysis = next(e["analysis"] for e in events(r) if e["type"] == "analysis")
    assert analysis["router"] == "heuristic"
    assert analysis["tasks"][0]["agent"] == "medical"
    assert any("longer than" in n for n in analysis["router_notes"])


def _picker(monkeypatch, fake_ollama, answer):
    """Answer circuit-picker calls with `answer`; everything else keeps the analyzer fake."""
    from nexgraft.llm.ollama import ollama

    analyzer = ollama.chat_json
    picks = []

    async def chat_json(model, messages, schema, options=None, timeout=120):
        if "anyOf" in schema:
            picks.append(messages[-1]["content"])
            return answer
        return await analyzer(model, messages, schema, options, timeout)

    monkeypatch.setattr(ollama, "chat_json", chat_json)
    return picks


def _hardware_run(message, options=None):
    with TestClient(app) as client:
        r = client.post("/api/run", json={"message": message, "agent": "hardware", "plugin": "electronics", "options": {"use_knowledge": False, **(options or {})}})
    return events(r)


def test_hardware_request_draws_schematic(fake_ollama, monkeypatch):
    picks = _picker(monkeypatch, fake_ollama, {"circuit": "led_resistor", "values": {"supply_v": "5 V", "forward_v": "2 V", "current_ma": "20 mA", "gain": "3"}})
    ev = _hardware_run("Draw an LED circuit for a 5 V supply at 20 mA")
    assert len(picks) == 1
    tool = next(e for e in ev if e["type"] == "tool")
    assert tool["tool"] == "led_resistor" and "gain" not in tool["input"]
    assert tool["output"]["schematic"]["svg"].startswith("<svg")
    assert [p["ref"] for p in tool["output"]["parts"]] == ["V1", "R1", "D1"]
    prompt = fake_ollama["chat"][0][-1]["content"]
    assert "How the circuit works" in prompt and "R1: 150 Ω" in prompt and "<svg" not in prompt


def test_schematic_skipped_when_off_topic_disabled_or_invalid(fake_ollama, monkeypatch):
    picks = _picker(monkeypatch, fake_ollama, {"circuit": "none", "values": {}})
    ev = _hardware_run("Compare aluminium and steel for a bracket")
    assert not picks and not any(e["type"] == "tool" for e in ev)  # no circuit words: no extra model call
    ev = _hardware_run("What should I consider in this circuit?")
    assert len(picks) == 1 and not any(e["type"] == "tool" for e in ev)
    ev = _hardware_run("Draw an LED circuit", {"diagrams": False})
    assert len(picks) == 1

    _picker(monkeypatch, fake_ollama, {"circuit": "led_resistor", "values": {"supply_v": "1.5 V", "forward_v": "2 V"}})
    ev = _hardware_run("Draw an LED circuit from a 1.5 V cell")
    notes = [e["message"] for e in ev if e["type"] == "note"]
    assert any("No LED series resistor schematic was drawn" in n for n in notes)


def test_schematic_guard_and_invented_values(fake_ollama, monkeypatch):
    # A pick that does not match the request is dropped, and unbuildable circuits skip the model entirely.
    picks = _picker(monkeypatch, fake_ollama, {"circuit": "linear_regulator", "values": {"vin_v": "24 V", "vout_v": "12 V"}})
    ev = _hardware_run("Circuit to control a 24 V lamp from an Arduino")
    assert len(picks) == 1 and not any(e["type"] == "tool" for e in ev)
    _hardware_run("Explain how a buck converter circuit works")
    assert len(picks) == 1

    # Unstated optional values are dropped; unstated logic voltages are kept but labelled.
    _picker(monkeypatch, fake_ollama, {"circuit": "voltage_divider", "values": {"vin_v": "9 V", "target_vout_v": "3.3 V", "r1_ohm": "1k", "load_ohm": "1k"}})
    ev = _hardware_run("Show a voltage divider circuit so a 3.3V ADC can read a 9V battery")
    tool = next(e for e in ev if e["type"] == "tool")
    assert tool["input"] == {"vin_v": 9.0, "target_vout_v": 3.3}
    assert tool["output"]["notes"][0].startswith("Default values used: R1 (top) = 10 kΩ.")
    _picker(monkeypatch, fake_ollama, {"circuit": "led_resistor", "values": {"supply_v": "3.3 V", "forward_v": "3 V", "current_ma": "10 mA"}})
    ev = _hardware_run("Draw a circuit to light a blue LED from an ESP32 pin at 10 mA")
    tool = next(e for e in ev if e["type"] == "tool")
    assert "Chosen by the model, not stated in your request: Supply voltage = 3.3 V; LED forward voltage = 3 V." in tool["output"]["notes"][0]
    _picker(monkeypatch, fake_ollama, {"circuit": "linear_regulator", "values": {"vin_v": "5 V", "vout_v": "3.3 V", "load_current_ma": "300 mA", "dropout_v": "0.3 V"}})
    ev = _hardware_run("Schematic of a 5 V to 3.3 V regulator for an ESP32 that draws 300 mA")
    note = next(e for e in ev if e["type"] == "tool")["output"]["notes"][0]
    assert note.startswith("Chosen by the model, not stated in your request: Dropout voltage = 300 mV.")
    assert "Thermal resistance θJA = 90 °C/W" in note
