"""Fine-tunes Qwen for NEXGRAFT workspaces: prepare -> train -> merge -> export -> evaluate.

    python -m finetune                                   # Bioinformatics and Hardware Design, full run
    python -m finetune --workspace hardware --quick      # small trial run
    python -m finetune --steps evaluate                  # re-run a single step

Steps whose output is already up to date are skipped, so an interrupted run resumes; --force redoes them.
"""

from __future__ import annotations

import argparse
import gc
import json
import shutil
import time
from pathlib import Path

from . import evaluate, export, merge, prepare, train
from .common import WORK, banner, ollama_has, recipe, work_dir
from .recipes import RECIPES

STEPS = {"prepare": prepare, "train": train, "merge": merge, "export": export, "evaluate": evaluate}
PREPARE_KEYS = ("examples", "eval_examples", "max_len", "min_score", "base", "seed")


def _at_least_as_new(a: Path, b: Path) -> bool:
    return a.is_file() and b.is_file() and a.stat().st_mtime >= b.stat().st_mtime


def up_to_date(step: str, ws: str, args: argparse.Namespace) -> bool:
    wd = work_dir(ws)
    if step == "prepare":
        meta = wd / "data" / "meta.json"
        return meta.is_file() and json.loads(meta.read_text(encoding="utf-8")) == {k: getattr(args, k) for k in PREPARE_KEYS}
    if step == "train":
        info = wd / "adapter" / "training.json"
        if not _at_least_as_new(info, wd / "data" / "train.jsonl"):
            return False
        t = json.loads(info.read_text(encoding="utf-8"))
        return not t.get("interrupted") and t.get("base") == args.base
    if step == "merge":
        return _at_least_as_new(wd / "merged" / "nexgraft.json", wd / "adapter" / "training.json")
    if step == "export":
        exported = wd / "exported.json"
        return (
            _at_least_as_new(exported, wd / "merged" / "nexgraft.json")
            and json.loads(exported.read_text(encoding="utf-8")).get("quantize") == args.quantize
            and ollama_has(recipe(ws).ollama_name) is not None
        )
    return False


def _free_gpu() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, conflict_handler="resolve")
    p.add_argument("--workspace", nargs="+", default=list(RECIPES), choices=list(RECIPES))
    p.add_argument("--steps", nargs="+", default=list(STEPS), choices=list(STEPS))
    p.add_argument("--quick", action="store_true", help="trial run: 300 conversations and a shorter evaluation")
    p.add_argument("--force", action="store_true", help="redo steps even when their output is up to date")
    for module in (prepare, train, export, evaluate):
        module.add_args(p)
    args = p.parse_args()
    if args.quick:
        args.examples, args.eval_examples, args.eval_limit = min(args.examples, 300), 30, 30
        args.mmlu_limit, args.held_out = min(args.mmlu_limit, 40), 1

    free_gb = shutil.disk_usage(WORK.parent if WORK.parent.exists() else Path.cwd()).free / 2**30
    banner(f"NEXGRAFT fine-tuning: {', '.join(args.workspace)} | steps: {', '.join(args.steps)} | base: {args.base}")
    print(f"Work folder: {WORK}  ({free_gb:.0f} GB free)")
    if free_gb < 25 and "train" in args.steps:
        print("Warning: a full run of both workspaces needs about 25-30 GB of free disk (base model, merged models, Ollama copies).")

    started = time.perf_counter()
    try:
        for ws in args.workspace:
            for step in args.steps:
                if not args.force and up_to_date(step, ws, args):
                    print(f"[{ws}] {step}: up to date, skipping (use --force to redo)")
                    continue
                STEPS[step].run(ws, args)
                if step == "train":
                    _free_gpu()
    finally:
        if not args.keep_reference:
            evaluate.remove_references()

    banner(f"Done in {(time.perf_counter() - started) / 60:.0f} min")
    for ws in args.workspace:
        name = recipe(ws).ollama_name
        report = work_dir(ws) / "eval_report.md"
        installed = "installed in Ollama" if ollama_has(name) else "not installed yet"
        print(f"- {name}: {installed}" + (f"; report: {report}" if report.is_file() else ""))
    print("Restart NEXGRAFT: each workspace uses its fine-tuned model automatically (Settings -> Per-workspace models to change).")


if __name__ == "__main__":
    main()
