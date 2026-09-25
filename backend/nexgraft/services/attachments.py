"""Stores uploaded attachments (original bytes + extracted text) under data/uploads/."""

from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from ..config import settings

_ID_RE = re.compile(r"^[a-f0-9]{16}$")


def safe_filename(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name).strip(" .") or "file"
    return name[:120]


class AttachmentStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, *, kind: str, name: str, data: bytes, text: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        att_id = uuid.uuid4().hex[:16]
        folder = self.root / att_id
        folder.mkdir(parents=True, exist_ok=True)
        filename = safe_filename(name)
        (folder / filename).write_bytes(data)
        record = {
            "id": att_id,
            "kind": kind,
            "name": filename,
            "size": len(data),
            "chars": len(text),
            "created": time.time(),
            "text": text,
            **(meta or {}),
        }
        (folder / "meta.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return self.public(record)

    def get(self, att_id: str) -> dict[str, Any] | None:
        if not _ID_RE.match(att_id or ""):
            return None
        path = self.root / att_id / "meta.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def original(self, att_id: str) -> tuple[str, bytes] | None:
        record = self.get(att_id)
        if not record:
            return None
        path = self.root / att_id / record["name"]
        return (record["name"], path.read_bytes()) if path.is_file() else None

    def resolve(self, ids: list[str]) -> list[dict[str, Any]]:
        return [r for r in (self.get(i) for i in ids[:10]) if r]

    @staticmethod
    def public(record: dict[str, Any]) -> dict[str, Any]:
        out = {k: v for k, v in record.items() if k != "text"}
        text = record.get("text", "")
        out["preview"] = text[:600]
        return out


attachment_store = AttachmentStore(settings.uploads_dir)
