"""Compares a fine-tuned model with its untouched base, both served by Ollama.

    python -m finetune.evaluate --workspace bioinformatics

By default the base is converted and quantized exactly like the fine-tuned model (a temporary
nexgraft-reference-* model), so any difference comes from fine-tuning, not from quantization.
Use --vs qwen2.5:3b to compare with another installed model instead.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .common import WORK, banner, ollama_api, ollama_cli, ollama_has, read_jsonl, recipe, work_dir
from .recipes import MMLU_CONTROL, ollama_base_for

MMLU_SYSTEM = "Answer the multiple-choice question. Reply with the letter of the correct option only."
LETTERS = "ABCD"
_created_references: set[str] = set()


def mmlu_questions(subject: str, limit: int) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq
    from huggingface_hub import hf_hub_download

    path = hf_hub_download("cais/mmlu", f"{subject}/test-00000-of-00001.parquet", repo_type="dataset")
    return pq.read_table(path).to_pylist()[:limit]


def _chat(model: str, system: str, user: str, options: dict[str, Any]) -> str:
    reply = ollama_api(
        "/api/chat",
        {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "options": options},
        timeout=900,
    )
    return reply.get("message", {}).get("content", "")


def mmlu_accuracy(model: str, questions: list[dict[str, Any]]) -> float:
    correct = 0
    for q in questions:
        options = "\n".join(f"{LETTERS[i]}. {c}" for i, c in enumerate(q["choices"]))
        text = _chat(model, MMLU_SYSTEM, f"{q['question']}\n\n{options}\n\nAnswer:", {"temperature": 0, "num_predict": 8, "num_ctx": 2048})
        m = re.search(r"\b([ABCD])\b", text)
        correct += bool(m and LETTERS.index(m.group(1)) == q["answer"])
    return correct / max(len(questions), 1)


def reference_model(base: str, quant: str) -> str:
    """Installs the untouched base with the same conversion and quantization as the fine-tuned model."""
    from huggingface_hub import snapshot_download

    from .export import install

    name = f"nexgraft-reference-{ollama_base_for(base).replace(':', '-')}-{quant}"
    if ollama_has(name):
        return name
    banner(f"Building the reference model {name} (untouched {base}, {quant})")
    out = WORK / "reference"
    out.mkdir(parents=True, exist_ok=True)
    install(Path(snapshot_download(base)), name, base, quant, None, out)
    _created_references.add(name)
    return name


def remove_references() -> None:
    cli = ollama_cli()
    for name in sorted(_created_references):
        if cli:
            subprocess.run([cli, "rm", name], check=False)
    _created_references.clear()


def run(workspace: str, args: argparse.Namespace) -> Path:
    r = recipe(workspace)
    wd = work_dir(workspace)
    exported_path = wd / "exported.json"
    if not ollama_has(r.ollama_name) or not exported_path.is_file():
        raise SystemExit(f"{r.ollama_name} is not installed in Ollama. Run: python -m finetune.export --workspace {workspace}")
    exported = json.loads(exported_path.read_text(encoding="utf-8"))
    tuned = r.ollama_name
    if args.vs:
        other = ollama_has(args.vs)
        if not other:
            raise SystemExit(f"{args.vs} is not installed in Ollama (ollama pull {args.vs}).")
    else:
        other = reference_model(exported["base"], exported["quantize"])
    banner(f"Evaluating {tuned} against {other}")

    subjects = list(r.mmlu) + [MMLU_CONTROL]
    questions = {s: mmlu_questions(s, args.mmlu_limit) for s in subjects}
    held_out = [row["messages"][1]["content"] for row in read_jsonl(wd / "data" / "eval.jsonl")[: args.held_out]]
    prompts = list(r.samples) + held_out

    scores: dict[str, dict[str, float]] = {}
    answers: dict[str, list[str]] = {}
    for model in (other, tuned):  # one model at a time, so a 4 GB GPU never holds both
        scores[model] = {}
        for s in subjects:
            scores[model][s] = mmlu_accuracy(model, questions[s])
            print(f"  {model:45s} MMLU {s:24s} {scores[model][s]:.1%}", flush=True)
        answers[model] = [_chat(model, r.identity, p, {"temperature": 0, "num_predict": args.max_tokens, "num_ctx": 4096}) for p in prompts]

    training = {}
    training_path = wd / "adapter" / "training.json"
    if training_path.is_file():
        training = json.loads(training_path.read_text(encoding="utf-8"))
    lines = [
        f"# Evaluation: {tuned} vs {other}",
        "",
        "| Benchmark | " + f"{other} | {tuned} | Change |",
        "|---|---|---|---|",
    ]
    for s in subjects:
        a, b = scores[other][s], scores[tuned][s]
        label = f"MMLU {s.replace('_', ' ')}" + (" (general-knowledge control)" if s == MMLU_CONTROL else "")
        lines.append(f"| {label}, n={len(questions[s])} | {a:.1%} | {b:.1%} | {100 * (b - a):+.1f} pts |")
    if training.get("eval_loss_after") is not None:
        lines.append(
            f"| Held-out Stack Exchange answers, loss (lower is better) | {training['eval_loss_before']:.3f} | "
            f"{training['eval_loss_after']:.3f} | {training['eval_loss_after'] - training['eval_loss_before']:+.3f} |"
        )
    lines += [
        "",
        f"With about {args.mmlu_limit} questions per subject, differences of a few points are within noise. The held-out loss "
        "measures how well the model predicts expert answers it never saw during training.",
        "",
        "## Side-by-side answers",
        "",
        f"System prompt: *{r.identity}* Greedy decoding, up to {args.max_tokens} tokens.",
    ]
    for i, prompt in enumerate(prompts):
        lines += ["", f"### {i + 1}. {prompt.splitlines()[0][:120]}", ""]
        if len(prompt.splitlines()) > 1 or len(prompt) > 120:
            lines += ["<details><summary>Full question</summary>", "", prompt, "", "</details>", ""]
        for model in (other, tuned):
            lines += [f"**{model}**", "", answers[model][i].strip(), ""]
    report = wd / "eval_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Report: {report}")
    return report


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--vs", default="", help="compare with this installed Ollama model instead of a matched reference")
    p.add_argument("--mmlu-limit", type=int, default=100, help="questions per MMLU subject")
    p.add_argument("--held-out", type=int, default=2, help="held-out questions to answer side by side")
    p.add_argument("--max-tokens", type=int, default=400, help="answer length for the side-by-side section")
    p.add_argument("--keep-reference", action="store_true", help="keep the nexgraft-reference-* model in Ollama afterwards")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", nargs="+", default=["bioinformatics", "hardware"])
    add_args(p)
    args = p.parse_args()
    try:
        for ws in args.workspace:
            run(ws, args)
    finally:
        if not args.keep_reference:
            remove_references()


if __name__ == "__main__":
    main()
