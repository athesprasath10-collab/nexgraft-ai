"""Merges the trained LoRA adapter into the Qwen base weights and saves a standalone model.

    python -m finetune.merge --workspace bioinformatics

Runs on the CPU in bf16, so the GPU is not needed. Qwen2.5-3B needs about 7 GB of free RAM here.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .common import banner, work_dir


def run(workspace: str, args: argparse.Namespace | None = None) -> Path:
    wd = work_dir(workspace)
    adapter = wd / "adapter"
    info_path = adapter / "training.json"
    if not info_path.is_file():
        raise SystemExit(f"No trained adapter in {adapter}. Run: python -m finetune.train --workspace {workspace}")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    base = info["base"]
    out = wd / "merged"
    banner(f"Merging the {workspace} adapter into {base}")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    model = AutoModelForCausalLM.from_pretrained(base, dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    if out.exists():
        shutil.rmtree(out)
    model.save_pretrained(out, max_shard_size="2GB")
    AutoTokenizer.from_pretrained(base).save_pretrained(out)
    (out / "nexgraft.json").write_text(json.dumps({"workspace": workspace, "base": base, "training": info}, indent=2), encoding="utf-8")
    size = sum(f.stat().st_size for f in out.glob("*.safetensors")) / 2**30
    print(f"Saved the merged model ({size:.1f} GB, safetensors) to {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", nargs="+", default=["bioinformatics", "hardware"])
    args = p.parse_args()
    for ws in args.workspace:
        run(ws, args)


if __name__ == "__main__":
    main()
