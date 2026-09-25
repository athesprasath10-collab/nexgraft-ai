import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from finetune.prepare import clean, parse_thread, reject_answer, reject_question  # noqa: E402
from finetune.recipes import RECIPES, ollama_base_for  # noqa: E402

THREAD = """# How do I merge ChIP-seq peaks across replicates?

(Asked by: username_0 on 2022-05-10)

I have 3 replicates. Which [bedops](https://bedops.readthedocs.io/x) option keeps peaks present in all of them?

**Tags:** bed, peak-calling

> **Comments:**
> **username_1**: try Genrich

---

## 2 answers

### Answer by username_5 on 2022-05-11. Score: 7 | Accepted answer

---

Use `bedops --intersect` on the three files:

```
bedops --intersect a.bed b.bed c.bed > common.bed
```

Source: <https://example.org/doc>

> **Comments:**
> **username_0**: thanks!

---

### Answer by username_2 on 2022-05-12. Score: 2

As @username_5 said, intersect works.
"""


def test_parse_thread_splits_question_and_answers():
    question, answers = parse_thread(THREAD)
    assert question.startswith("I have 3 replicates.") and "Tags" not in question and "Comments" not in question
    assert [(s, acc) for s, acc, _ in answers] == [(7, True), (2, False)]
    body = answers[0][2]
    assert body.startswith("Use `bedops --intersect`") and "thanks!" not in body and not body.endswith("---")


def test_clean_drops_links_and_mentions():
    text = clean("See [the docs](https://x.org/a) and <https://x.org/b> now.\n\nSource: <https://x.org/c>\n\n\n\n@username_3: yes")
    assert "http" not in text
    assert "See the docs and  now." in text
    assert "Source" not in text and "\n\n\n" not in text and text.endswith("yes")


def test_answer_filters():
    ok = "A self-contained explanation of the method. " * 5
    assert reject_answer(ok, ok) is None
    assert reject_answer(ok, ok + " As the other answer says.") == "answer refers to the thread"
    assert reject_answer("![plot](https://i.sstatic.net/a.png) " + ok, ok) == "answer has an image"
    py2 = ok + "\n```python\nprint 'hello'\n```\n"
    assert reject_answer(py2, py2) == "Python 2 code"
    old = ok + "\n```python\nfrom Bio.SeqUtils import GC\n```\n"
    assert reject_answer(old, old) == "removed Biopython API"
    assert reject_question("Why?") == "question length"


def test_recipes_and_ollama_names():
    assert set(RECIPES) == {"bioinformatics", "hardware"}
    assert abs(sum(s.share for s in RECIPES["hardware"].sources) - 1) < 1e-9
    assert all(r.ollama_name == f"nexgraft-{ws}" for ws, r in RECIPES.items())
    assert ollama_base_for("Qwen/Qwen2.5-3B-Instruct") == "qwen2.5:3b"
    assert ollama_base_for("Qwen/Qwen2.5-1.5B-Instruct") == "qwen2.5:1.5b"
    assert ollama_base_for("Qwen/Qwen2.5-Coder-3B-Instruct") == "qwen2.5-coder:3b"
