"""Builds chat-format training data for a workspace from Stack Exchange Q&A hosted on Hugging Face.

    python -m finetune.prepare --workspace bioinformatics
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .common import banner, recipe, work_dir, write_jsonl
from .recipes import DEFAULT_BASE, SE_LICENSE, SE_REPO, Recipe, Source

ANSWERS_SECTION = re.compile(r"^## \d+ answers?[ \t]*$", re.M)
ANSWER_HEADER = re.compile(r"^### Answer by .*?\. Score: (-?\d+)( \| Accepted answer)?[ \t]*$", re.M)
ASKED_BY = re.compile(r"^\(Asked by: [^\n]*\)[ \t]*$", re.M)
TAGS_LINE = re.compile(r"^\*\*Tags:\*\*", re.M)
COMMENTS = re.compile(r"^> \*\*Comments:\*\*", re.M)

IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)|i\.sstatic\.net|i\.stack\.imgur\.com")
LINK = re.compile(r"\[([^\]\n]+)\]\((?:https?://|/)[^)\s]*(?: \"[^\"]*\")?\)")
AUTOLINK_LINE = re.compile(r"^[^\n<]{0,40}<https?://[^>\s]+>[ \t]*$", re.M)
AUTOLINK = re.compile(r"<https?://[^>\s]+>")
MENTION = re.compile(r"@username_\d+\b[:,]?[ \t]*")
BLANK_LINES = re.compile(r"\n{3,}")
CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.S)

# Answers that only make sense inside the original thread.
THREAD_REFERENCE = re.compile(
    r"username_\d+|\b(?:other|above|below|previous|accepted|existing|earlier) answers?\b|\b(?:my|this) answer\b"
    r"|'s answer\b|\bthe OP\b|\bOP's\b|\bcomments? (?:above|below)\b"
    r"|\b(?:your|the) (?:previous|other|earlier) question\b|\byou (?:previously|already) asked\b|\bduplicate\b",
    re.I,
)
PYTHON2_PRINT = re.compile(r"^\s*print [\"'A-Za-z_]", re.M)
REMOVED_BIOPYTHON_GC = re.compile(r"from Bio\.SeqUtils import [^\n]*\bGC\b(?!_)|SeqUtils\.GC\(")


def _cut(text: str, pattern: re.Pattern[str]) -> str:
    m = pattern.search(text)
    return text[: m.start()] if m else text


def _strip_rules(text: str) -> str:
    text = text.strip()
    while text.startswith("---"):
        text = text[3:].lstrip()
    while text.endswith("---"):
        text = text[:-3].rstrip()
    return text


def parse_thread(text: str) -> tuple[str, list[tuple[int, bool, str]]] | None:
    """Splits a ThreadText into the question body and (score, accepted, body) answers."""
    section = ANSWERS_SECTION.search(text)
    if not section:
        return None
    head, tail = text[: section.start()], text[section.end():]
    asked = ASKED_BY.search(head)
    body = head[asked.end():] if asked else head.split("\n", 1)[-1]
    question = _strip_rules(_cut(_cut(body, TAGS_LINE), COMMENTS))

    headers = list(ANSWER_HEADER.finditer(tail))
    answers = []
    for i, h in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(tail)
        answers.append((int(h.group(1)), bool(h.group(2)), _strip_rules(_cut(tail[h.end():end], COMMENTS))))
    return question, answers


def clean(text: str) -> str:
    """Links become plain text and URLs are dropped, so the model does not learn to invent links."""
    text = LINK.sub(r"\1", text)
    text = AUTOLINK_LINE.sub("", text)
    text = AUTOLINK.sub("", text)
    text = MENTION.sub("", text)
    return BLANK_LINES.sub("\n\n", text).strip()


def reject_question(raw: str) -> str | None:
    if IMAGE.search(raw):
        return "question has an image"
    if not 30 <= len(raw) <= 4000:
        return "question length"
    return None


def reject_answer(raw: str, cleaned: str) -> str | None:
    if IMAGE.search(raw):
        return "answer has an image"
    if THREAD_REFERENCE.search(cleaned):
        return "answer refers to the thread"
    if not 150 <= len(cleaned) <= 6000:
        return "answer length"
    code = "\n".join(CODE_BLOCK.findall(cleaned))
    if PYTHON2_PRINT.search(code):
        return "Python 2 code"
    if REMOVED_BIOPYTHON_GC.search(cleaned):
        return "removed Biopython API"
    return None


def _tags(raw: str | None) -> set[str]:
    return set(re.findall(r"[^<>|]+", raw or ""))


def _download(filename: str) -> Path:
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(SE_REPO, filename=filename, repo_type="dataset"))


def candidates(src: Source, min_score: int, stats: Counter) -> list[dict[str, Any]]:
    """Best answer per usable question, best-scored first."""
    import pyarrow.parquet as pq

    out: list[dict[str, Any]] = []
    columns = ["Id", "Title", "Tags", "Score", "ClosedDate", "ContentLicense", "ThreadText"]
    for filename in src.files:
        print(f"Downloading {SE_REPO}/{filename} (cached after the first run)...", flush=True)
        path = _download(filename)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=512, columns=columns):
            for row in batch.to_pylist():
                stats["threads"] += 1
                if row["ClosedDate"] or (row["Score"] or 0) < 1:
                    stats["closed or low-scored question"] += 1
                    continue
                if src.tags and not (_tags(row["Tags"]) & src.tags):
                    stats["outside the topic tags"] += 1
                    continue
                parsed = parse_thread(row["ThreadText"] or "")
                if not parsed:
                    continue
                question_raw, answers = parsed
                reason = reject_question(question_raw)
                if reason:
                    stats[reason] += 1
                    continue
                ranked = sorted(
                    (a for a in answers if a[0] >= min_score or (a[1] and a[0] >= 1)),
                    key=lambda a: a[0] + (2 if a[1] else 0),
                    reverse=True,
                )
                if not ranked:
                    stats["no well-scored answer"] += 1
                    continue
                for score, accepted, raw in ranked:
                    answer = clean(raw)
                    reason = reject_answer(raw, answer)
                    if reason:
                        stats[reason] += 1
                        continue
                    out.append(
                        {
                            "user": f"{(row['Title'] or '').strip()}\n\n{clean(question_raw)}".strip(),
                            "assistant": answer,
                            "rank": score + (2 if accepted else 0),
                            "source": f"https://{src.site}/q/{row['Id']}",
                            "license": row["ContentLicense"] or SE_LICENSE,
                        }
                    )
                    break
    out.sort(key=lambda c: c["rank"], reverse=True)
    return out


def _token_counter(base: str):
    try:
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(base)
    except Exception as exc:  # offline or transformers missing: fall back to a character estimate
        print(f"Tokenizer unavailable ({exc}); estimating lengths from characters.")
        return lambda messages: sum(len(m["content"]) for m in messages) // 3 + 20
    return lambda messages: len(tok(tok.apply_chat_template(messages, tokenize=False), add_special_tokens=False)["input_ids"])


def build(r: Recipe, examples: int, eval_examples: int, max_len: int, base: str, min_score: int, seed: int) -> dict[str, Any]:
    count_tokens = _token_counter(base)
    stats: Counter = Counter()
    rows: list[dict[str, Any]] = []
    per_site: dict[str, int] = {}
    carry = 0
    total = examples + eval_examples
    for i, src in enumerate(r.sources):
        quota = (total - len(rows)) if i == len(r.sources) - 1 else round(src.share * total) + carry
        picked = 0
        for c in candidates(src, min_score, stats):
            if picked >= quota:
                break
            messages = [
                {"role": "system", "content": r.identity},
                {"role": "user", "content": c["user"]},
                {"role": "assistant", "content": c["assistant"]},
            ]
            if count_tokens(messages) > max_len:
                stats["longer than max length"] += 1
                continue
            rows.append({"messages": messages, "source": c["source"], "license": c["license"]})
            picked += 1
        per_site[src.site] = picked
        carry = quota - picked
        print(f"{src.site}: {picked} examples (wanted {quota})", flush=True)

    random.Random(seed).shuffle(rows)
    n_eval = min(eval_examples, max(1, len(rows) // 10))
    scanned = stats.pop("threads", 0)
    return {"train": rows[n_eval:], "eval": rows[:n_eval], "per_site": per_site, "scanned": scanned, "skipped": dict(stats)}


def write_data_card(path: Path, r: Recipe, result: dict[str, Any], args: argparse.Namespace) -> None:
    lines = [
        f"# Training data: {r.workspace}",
        "",
        f"{len(result['train'])} training and {len(result['eval'])} evaluation conversations, built by `finetune/prepare.py`.",
        "",
        "| Source | Examples | License |",
        "|---|---|---|",
    ]
    for site, n in result["per_site"].items():
        lines.append(f"| {site} | {n} | {SE_LICENSE} |")
    lines += [
        "",
        f"Questions and answers were written by Stack Exchange contributors and obtained from the Hugging Face dataset "
        f"[{SE_REPO}](https://huggingface.co/datasets/{SE_REPO}). Each JSONL row links to its original question in `source`. "
        "Content is licensed under Creative Commons Attribution-ShareAlike; keep this attribution if you share the data "
        "or models trained on it.",
        "",
        "Selection: open questions with a positive score and no images; the best-scored (or accepted) answer that "
        "stands on its own; links reduced to their text; Python 2 code and removed Biopython APIs dropped; conversations "
        f"longer than {args.max_len} tokens dropped.",
        "",
        f"Scanned {result['scanned']} threads. Skipped while building:",
        "",
    ]
    lines += [f"- {k}: {v}" for k, v in sorted(result["skipped"].items(), key=lambda kv: -kv[1])]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--examples", type=int, default=1500, help="training conversations per workspace")
    p.add_argument("--eval-examples", type=int, default=60, help="held-out conversations for evaluation loss")
    p.add_argument("--max-len", type=int, default=1024, help="maximum tokens per conversation")
    p.add_argument("--min-score", type=int, default=2, help="minimum answer score (accepted answers need 1)")
    p.add_argument("--base", default=DEFAULT_BASE, help="Hugging Face base model (for token counting)")
    p.add_argument("--seed", type=int, default=42)


def run(workspace: str, args: argparse.Namespace) -> Path:
    r = recipe(workspace)
    out = work_dir(workspace) / "data"
    out.mkdir(exist_ok=True)
    banner(f"Preparing training data for {workspace}")
    result = build(r, args.examples, args.eval_examples, args.max_len, args.base, args.min_score, args.seed)
    if len(result["train"]) < 50:
        raise SystemExit(f"Only {len(result['train'])} usable examples were found; lower --min-score or check the download.")
    write_jsonl(out / "train.jsonl", result["train"])
    write_jsonl(out / "eval.jsonl", result["eval"])
    write_data_card(out / "DATA_CARD.md", r, result, args)
    meta = {k: getattr(args, k) for k in ("examples", "eval_examples", "max_len", "min_score", "base", "seed")}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Wrote {len(result['train'])} train / {len(result['eval'])} eval conversations to {out}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--workspace", nargs="+", default=["bioinformatics", "hardware"])
    add_args(p)
    args = p.parse_args()
    for ws in args.workspace:
        run(ws, args)


if __name__ == "__main__":
    main()
