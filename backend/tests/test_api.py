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
