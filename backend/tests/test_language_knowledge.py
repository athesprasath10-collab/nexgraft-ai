import asyncio

from nexgraft.llm.ollama import ThinkStripper
from nexgraft.multimodal.documents import chunk_text, extract_text
from nexgraft.multimodal.language import detect_language, resolve_language


def test_language_detection():
    assert detect_language("Explain Newton's laws") == "en"
    assert detect_language("நியூட்டனின் விதிகளை விளக்குங்கள்") == "ta"
    assert detect_language("न्यूटन के नियम समझाइए") == "hi"
    assert detect_language("DNA வரிசையின் GC அளவு என்ன?") == "ta"
    lang, auto = resolve_language("te", "hello")
    assert lang.code == "te" and auto is False


def test_think_stripper_handles_split_tags():
    s = ThinkStripper()
    out = "".join(s.feed(p) for p in ["<thi", "nk>secret", " reasoning</th", "ink>\nAnswer", " <", "b>ok"]) + s.flush()
    assert out == "Answer <b>ok"


def test_chunking_respects_headings():
    text = "# Title\n\n## A\nshort text\n\n## B\n" + ("sentence number one is here. " * 120)
    chunks = chunk_text(text, target=500, overlap=50)
    assert chunks[0]["heading"] == "A"
    assert all(c["heading"] in {"A", "B"} for c in chunks)
    assert len(chunks) >= 4
    assert all(len(c["text"]) <= 900 for c in chunks)


def test_extract_text_formats():
    assert "hello" in extract_text(b"# hello\n", "a.md")
    csv = extract_text(b"gene,value\nTP53,1\n", "a.csv")
    assert "1 data rows" in csv and "gene" in csv


def test_keyword_knowledge_base(tmp_path):
    from nexgraft.knowledge.store import KnowledgeBase

    class NoEmbeddings:
        async def has_model(self, name):
            return False

    root = tmp_path / "knowledge"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "sensors.md").write_text("# Sensors\n\n## PPG\nPhotoplethysmography measures pulse with LEDs.\n\n## Beams\nSteel beams carry loads.\n")
    kb = KnowledgeBase(root, tmp_path / "index", NoEmbeddings())
    asyncio.run(kb.build())
    assert kb.mode == "keyword"
    hits = asyncio.run(kb.search("photoplethysmography pulse LEDs", ["demo"], min_bm25=0.1))
    assert hits and hits[0][0].heading == "PPG"
    assert asyncio.run(kb.search("quantum chromodynamics", ["demo"])) == []


def test_ollama_host_normalisation():
    from nexgraft.config import _ollama_url

    assert _ollama_url("") == "http://127.0.0.1:11434"
    assert _ollama_url("0.0.0.0") == "http://127.0.0.1:11434"
    assert _ollama_url("0.0.0.0:11500") == "http://127.0.0.1:11500"
    assert _ollama_url("http://192.168.1.5:11434/") == "http://192.168.1.5:11434"
    assert _ollama_url("localhost") == "http://localhost:11434"
