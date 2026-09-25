"""Converts the merged model to GGUF and installs it in Ollama as nexgraft-<workspace>.

    python -m finetune.export --workspace bioinformatics

Default quantization is q5_0 for the weights with 8-bit embeddings: about 2.2 GB for Qwen2.5-3B, which fits
a 4 GB GPU with room for the context, at quality comparable to the q4_K_M build of qwen2.5:3b.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from urllib.error import URLError

from .common import banner, ollama_api, ollama_cli, recipe, work_dir
from .gguf_convert import QUANTS, convert
from .recipes import ollama_base_for

# Used only when no Qwen2.5 model is installed in Ollama to copy the chat template from.
CHATML_TEMPLATE = """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}
{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""


def _template(template_from: str) -> tuple[str, str]:
    try:
        installed = [m["name"] for m in ollama_api("/api/tags", timeout=10).get("models", [])]
    except (OSError, URLError) as exc:
        raise SystemExit("Ollama is not running. Open the Ollama app (or run `ollama serve`) and retry.") from exc
    candidates = [template_from] + [m for m in installed if m.startswith("qwen2.5") and "vl" not in m]
    for name in candidates:
        if name in installed or f"{name}:latest" in installed:
            template = ollama_api("/api/show", {"model": name}, timeout=30).get("template")
            if template:
                return template, name
    return CHATML_TEMPLATE, "built-in ChatML"


def install(model_dir: Path, name: str, base: str, quant: str, system: str | None, out_dir: Path, keep_gguf: bool = False) -> None:
    """Converts a Qwen2 Hugging Face model directory to GGUF (written to `out_dir`) and creates the Ollama model `name`."""
    cli = ollama_cli()
    if not cli:
        raise SystemExit("The `ollama` command was not found. Install Ollama from https://ollama.com/download")
    template, origin = _template(ollama_base_for(base))
    gguf_path = out_dir / f"{name}-{quant}.gguf"
    print(f"Converting to GGUF ({quant}); this takes a few minutes for a 3B model...", flush=True)
    convert(model_dir, gguf_path, name, quant)
    print(f"Wrote {gguf_path.name} ({gguf_path.stat().st_size / 2**30:.2f} GB). Chat template copied from {origin}.")

    lines = [f"FROM {gguf_path.resolve().as_posix()}", f'TEMPLATE """{template}"""']
    if system:
        lines.append(f'SYSTEM """{system}"""')
    lines += ['PARAMETER stop "<|im_start|>"', 'PARAMETER stop "<|im_end|>"', 'PARAMETER stop "<|endoftext|>"']
    modelfile = out_dir / f"Modelfile.{name}"
    modelfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [cli, "create", name, "-f", str(modelfile)]
    print(" ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=out_dir)
    if result.returncode != 0:
        raise SystemExit(f"`ollama create` failed. The GGUF file is kept at {gguf_path}; check that Ollama is running and retry.")
    if not keep_gguf:
        gguf_path.unlink()  # Ollama keeps its own copy


def run(workspace: str, args: argparse.Namespace) -> str:
    r = recipe(workspace)
    wd = work_dir(workspace)
    merged = wd / "merged"
    if not (merged / "config.json").is_file():
        raise SystemExit(f"No merged model in {merged}. Run: python -m finetune.merge --workspace {workspace}")
    base = json.loads((merged / "nexgraft.json").read_text(encoding="utf-8"))["base"]
    banner(f"Installing {r.ollama_name} in Ollama")
    install(merged, r.ollama_name, base, args.quantize, r.identity, wd, args.keep_gguf)

    reply = ollama_api(
        "/api/chat",
        {
            "model": r.ollama_name,
            "messages": [{"role": "user", "content": "In one sentence, what do you help with?"}],
            "options": {"temperature": 0, "num_predict": 60},
        },
        timeout=600,
    )
    print(f"Test reply from {r.ollama_name}: {reply.get('message', {}).get('content', '').strip()}")
    (wd / "exported.json").write_text(json.dumps({"model": r.ollama_name, "quantize": args.quantize, "base": base}, indent=2), encoding="utf-8")
    return r.ollama_name


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--quantize", default="q5_0", choices=QUANTS, help="q5_0 fits a 4 GB GPU; q8_0 (~3.3 GB for 3B) is closer to full precision")
    p.add_argument("--keep-gguf", action="store_true", help="keep the .gguf file (e.g. for LM Studio or llama.cpp)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", nargs="+", default=["bioinformatics", "hardware"])
    add_args(p)
    args = p.parse_args()
    for ws in args.workspace:
        run(ws, args)


if __name__ == "__main__":
    main()
