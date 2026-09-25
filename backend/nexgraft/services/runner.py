"""User-triggered local Python runner for the Bioinformatics workspace.

This is NOT a security sandbox: code runs as a separate Python process with
your user permissions, inside a temporary folder, with a timeout. It only runs
when the user reviews the code and presses Run in the UI.
"""

from __future__ import annotations

import asyncio
import base64
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

MAX_OUTPUT = 60_000
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".gif": "image/gif"}
TEXT_TYPES = {".csv", ".tsv", ".txt", ".fasta", ".fa", ".json", ".md", ".log"}


def _clip(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + f"\n… (output truncated, {len(text)} chars)"


def _run_sync(code: str, files: list[tuple[str, bytes]], timeout: int) -> dict[str, Any]:
    workdir = Path(tempfile.mkdtemp(prefix="nexgraft-run-"))
    try:
        for name, data in files:
            (workdir / name).write_bytes(data)
        script = workdir / "nexgraft_script.py"
        script.write_text(code, encoding="utf-8")
        before = {p.name for p in workdir.iterdir()}
        env = os.environ.copy()
        env.update({"MPLBACKEND": "Agg", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"})
        started = time.perf_counter()
        timed_out = False
        try:
            proc = subprocess.run(
                [sys.executable, script.name],
                cwd=workdir,
                env=env,
                capture_output=True,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
            )
            stdout = proc.stdout.decode("utf-8", "replace")
            stderr = proc.stderr.decode("utf-8", "replace")
            code_ = proc.returncode
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or b"").decode("utf-8", "replace")
            stderr = (exc.stderr or b"").decode("utf-8", "replace") + f"\nStopped after {timeout} s (timeout)."
            code_ = None
        artifacts: list[dict[str, Any]] = []
        budget = 6 * 1024 * 1024
        for path in sorted(workdir.iterdir()):
            if path.name in before or not path.is_file():
                continue
            ext = path.suffix.lower()
            size = path.stat().st_size
            if ext in IMAGE_TYPES and size <= budget:
                budget -= size
                data = base64.b64encode(path.read_bytes()).decode()
                artifacts.append({"name": path.name, "type": "image", "size": size, "data_url": f"data:{IMAGE_TYPES[ext]};base64,{data}"})
            elif ext in TEXT_TYPES:
                artifacts.append({"name": path.name, "type": "text", "size": size, "preview": path.read_text("utf-8", "replace")[:20_000]})
            else:
                artifacts.append({"name": path.name, "type": "file", "size": size})
        return {
            "exit_code": code_,
            "timed_out": timed_out,
            "stdout": _clip(stdout),
            "stderr": _clip(stderr),
            "seconds": round(time.perf_counter() - started, 2),
            "artifacts": artifacts,
            "python": sys.version.split()[0],
        }
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def run_python(code: str, files: list[tuple[str, bytes]], timeout: int) -> dict[str, Any]:
    return await asyncio.to_thread(_run_sync, code, files, timeout)
