"""QLoRA fine-tuning sized for a 4 GB NVIDIA GPU (GTX 1650 Ti class).

    python -m finetune.train --workspace bioinformatics

Memory plan for Qwen2.5-3B on 4 GB: the base model is loaded in 4-bit NF4 (~2.1 GB), only small LoRA
adapters are trained (fp32, 8-bit optimizer states), activations are recomputed (gradient checkpointing),
and the loss is computed in vocabulary chunks so full logits are never held in memory.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import platform
import random
import time
from pathlib import Path
from typing import Any

from .common import banner, ollama_unload_all, read_jsonl, recipe, work_dir
from .recipes import DEFAULT_BASE

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def encode(tok, messages: list[dict[str, str]]) -> tuple[list[int], list[int]]:
    """Token ids and labels for one conversation; only the assistant reply is trained on."""
    prompt = tok.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(messages, tokenize=False)
    if not full.startswith(prompt):
        raise ValueError("The chat template does not render the prompt as a prefix of the conversation.")
    prompt_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    reply_ids = tok(full[len(prompt):], add_special_tokens=False)["input_ids"]
    return prompt_ids + reply_ids, [-100] * len(prompt_ids) + reply_ids


def _chunk_loss(hidden, weight, target):
    import torch.nn.functional as F

    return F.cross_entropy((hidden @ weight.t()).float(), target, reduction="sum")


def sequence_loss(model, input_ids, labels, chunk: int = 256):
    """Summed next-token loss over the labelled positions of a single sequence."""
    import torch
    from torch.utils.checkpoint import checkpoint

    base = model.get_base_model()
    hidden = base.get_decoder()(input_ids=input_ids).last_hidden_state[0, :-1]
    target = labels[0, 1:]
    keep = target != -100
    hidden, target = hidden[keep], target[keep]
    weight = base.get_output_embeddings().weight
    total = torch.zeros((), dtype=torch.float32, device=hidden.device)
    for i in range(0, target.numel(), chunk):
        args = (hidden[i:i + chunk], weight, target[i:i + chunk])
        total = total + (checkpoint(_chunk_loss, *args, use_reentrant=False) if torch.is_grad_enabled() else _chunk_loss(*args))
    return total


def load_model(base: str, use_4bit: bool, device: str, dtype):
    from transformers import AutoModelForCausalLM

    kwargs: dict[str, Any] = {"dtype": dtype, "attn_implementation": "sdpa"}
    if use_4bit:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=dtype,
        )
        kwargs["device_map"] = {"": 0}
    model = AutoModelForCausalLM.from_pretrained(base, **kwargs)
    if not use_4bit:
        model.to(device)
    model.config.use_cache = False
    for p in model.parameters():
        p.requires_grad_(False)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    return model


def make_optimizer(params, lr: float, device: str):
    import torch

    if device == "cuda":
        try:
            import bitsandbytes as bnb

            return bnb.optim.AdamW8bit(params, lr=lr, weight_decay=0.0), "AdamW 8-bit"
        except Exception:
            pass
    return torch.optim.AdamW(params, lr=lr, weight_decay=0.0), "AdamW"


def evaluate_loss(model, data: list[tuple[list[int], list[int]]], device: str, amp) -> float:
    import torch

    model.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for ids, labels in data:
            with amp():
                loss = sequence_loss(model, torch.tensor([ids], device=device), torch.tensor([labels], device=device))
            total += loss.item()
            count += sum(1 for x in labels[1:] if x != -100)
    model.train()
    return total / max(count, 1)


def run(workspace: str, args: argparse.Namespace) -> Path:
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoTokenizer

    if platform.system() != "Windows":
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    r = recipe(workspace)
    wd = work_dir(workspace)
    data_dir = wd / "data"
    if not (data_dir / "train.jsonl").is_file():
        raise SystemExit(f"No training data in {data_dir}. Run: python -m finetune.prepare --workspace {workspace}")
    out = wd / "adapter"
    banner(f"Fine-tuning {args.base} for {workspace} ({r.ollama_name})")

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu" and not args.allow_cpu:
        raise SystemExit(
            "No CUDA GPU is visible to PyTorch. Install the CUDA build of PyTorch (finetune.bat does this) and check "
            "that `nvidia-smi` works. Pass --allow-cpu only for a tiny smoke test."
        )
    if device == "cuda":
        dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16
        props = torch.cuda.get_device_properties(0)
        print(f"GPU: {props.name}, {props.total_memory / 2**30:.1f} GB, compute {props.major}.{props.minor}, {str(dtype).split('.')[-1]}")
        ollama_unload_all()
    else:
        dtype = torch.float32
        print("Running on CPU (smoke test only).")
    use_4bit = device == "cuda" and not args.no_4bit

    tok = AutoTokenizer.from_pretrained(args.base)
    train = [encode(tok, row["messages"]) for row in read_jsonl(data_dir / "train.jsonl")]
    evals = [encode(tok, row["messages"]) for row in read_jsonl(data_dir / "eval.jsonl")]
    train = [t for t in train if len(t[0]) <= args.max_len]
    evals = [t for t in evals if len(t[0]) <= args.max_len][: args.eval_limit]
    if args.limit:
        train = train[: args.limit]
    trained_tokens = [sum(1 for x in labels[1:] if x != -100) for _, labels in train]
    steps_per_epoch = math.ceil(len(train) / args.grad_accum)
    total_steps = min(args.max_steps or 10**9, steps_per_epoch * args.epochs)
    print(f"{len(train)} conversations, {sum(len(t[0]) for t in train):,} tokens per epoch, {total_steps} optimizer steps")

    model = load_model(args.base, use_4bit, device, dtype)
    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=LORA_TARGETS,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    params = [p for p in model.parameters() if p.requires_grad]
    for p in params:
        p.data = p.data.float()
    n_params = sum(p.numel() for p in params)
    optimizer, opt_name = make_optimizer(params, args.lr, device)
    warmup = max(1, round(total_steps * 0.05))

    def lr_factor(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        progress = (step - warmup) / max(1, total_steps - warmup)
        return 0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_factor)
    scaler = torch.amp.GradScaler("cuda", enabled=device == "cuda" and dtype == torch.float16)

    def amp():
        return torch.autocast(device_type="cuda", dtype=dtype) if device == "cuda" else contextlib.nullcontext()

    print(f"LoRA r={args.lora_r} alpha={args.lora_alpha}: {n_params / 1e6:.1f}M trainable parameters, {opt_name}, lr {args.lr}")
    model.train()
    log_path = wd / "train_log.jsonl"
    log_path.write_text("", encoding="utf-8")
    eval_start = evaluate_loss(model, evals, device, amp) if evals else None
    if eval_start is not None:
        print(f"Held-out loss before training: {eval_start:.4f}")
        log_path.write_text(json.dumps({"step": 0, "eval_loss": eval_start}) + "\n", encoding="utf-8")

    started = time.perf_counter()
    step, skipped_windows, seen_tokens = 0, 0, 0
    interrupted = False
    try:
        for _epoch in range(args.epochs):
            order = list(range(len(train)))
            random.shuffle(order)
            for w in range(0, len(order), args.grad_accum):
                if step >= total_steps:
                    break
                window = order[w:w + args.grad_accum]
                denom = sum(trained_tokens[i] for i in window)
                window_loss, oom = 0.0, False
                try:
                    for i in window:
                        ids, labels = train[i]
                        with amp():
                            loss = sequence_loss(model, torch.tensor([ids], device=device), torch.tensor([labels], device=device))
                        scaler.scale(loss / denom).backward()
                        window_loss += loss.item()
                        seen_tokens += len(ids)
                except torch.cuda.OutOfMemoryError:
                    oom = True
                if oom:
                    loss = None
                    optimizer.zero_grad(set_to_none=True)
                    torch.cuda.empty_cache()
                    skipped_windows += 1
                    print(f"  out of GPU memory on step {step + 1}; skipped it ({skipped_windows} so far)")
                    if skipped_windows > 10:
                        raise SystemExit(
                            "Repeatedly out of GPU memory. Close other GPU apps, or retry with --max-len 768, "
                            "or a smaller base: --base Qwen/Qwen2.5-1.5B-Instruct"
                        )
                    continue
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()
                step += 1

                entry: dict[str, Any] = {"step": step, "loss": round(window_loss / max(denom, 1), 4), "lr": scheduler.get_last_lr()[0]}
                if step % args.log_every == 0 or step == total_steps:
                    elapsed = time.perf_counter() - started
                    eta = elapsed / step * (total_steps - step)
                    mem = f", GPU peak {torch.cuda.max_memory_allocated() / 2**30:.2f} GB" if device == "cuda" else ""
                    print(
                        f"  step {step}/{total_steps}  loss {entry['loss']:.4f}  lr {entry['lr']:.2e}  "
                        f"{seen_tokens / elapsed:,.0f} tok/s  {elapsed / 60:.1f} min elapsed, ~{eta / 60:.0f} min left{mem}",
                        flush=True,
                    )
                if evals and args.eval_every and step % args.eval_every == 0 and step != total_steps:
                    entry["eval_loss"] = evaluate_loss(model, evals, device, amp)
                    print(f"  held-out loss: {entry['eval_loss']:.4f}")
                with log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
    except KeyboardInterrupt:
        interrupted = True
        print("\nInterrupted: saving the adapter trained so far.")

    eval_end = evaluate_loss(model, evals, device, amp) if evals and not interrupted else None
    if eval_end is not None:
        print(f"Held-out loss after training: {eval_end:.4f} (before: {eval_start:.4f})")
    model.save_pretrained(out)
    summary = {
        "workspace": workspace,
        "base": args.base,
        "steps": step,
        "planned_steps": total_steps,
        "interrupted": interrupted,
        "conversations": len(train),
        "minutes": round((time.perf_counter() - started) / 60, 1),
        "eval_loss_before": eval_start,
        "eval_loss_after": eval_end,
        "skipped_oom_steps": skipped_windows,
        "device": torch.cuda.get_device_name(0) if device == "cuda" else platform.processor() or "cpu",
        "hyperparameters": {k: getattr(args, k) for k in ("lr", "epochs", "grad_accum", "max_len", "lora_r", "lora_alpha", "lora_dropout", "seed")},
    }
    (out / "training.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Saved LoRA adapter to {out}")
    if interrupted:
        raise SystemExit(130)
    return out


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--base", default=DEFAULT_BASE, help="Hugging Face base model")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--lr", type=float, default=1e-4, help="learning rate (low = a light touch)")
    p.add_argument("--grad-accum", type=int, default=16, help="conversations per optimizer step")
    p.add_argument("--max-len", type=int, default=1024)
    p.add_argument("--lora-r", type=int, default=16)
    p.add_argument("--lora-alpha", type=int, default=32)
    p.add_argument("--lora-dropout", type=float, default=0.05)
    p.add_argument("--max-steps", type=int, default=0, help="stop after this many optimizer steps (0 = full run)")
    p.add_argument("--limit", type=int, default=0, help="use only the first N training conversations")
    p.add_argument("--eval-limit", type=int, default=60)
    p.add_argument("--eval-every", type=int, default=0, help="held-out loss every N steps (0 = start and end only)")
    p.add_argument("--log-every", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--no-4bit", action="store_true", help="train on full-precision weights (needs far more memory)")
    p.add_argument("--allow-cpu", action="store_true", help=argparse.SUPPRESS)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", nargs="+", default=["bioinformatics", "hardware"])
    add_args(p)
    args = p.parse_args()
    for ws in args.workspace:
        run(ws, args)


if __name__ == "__main__":
    main()
