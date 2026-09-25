"""Text extraction for uploaded documents (PDF, DOCX, text-like formats)."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".py", ".r", ".ipynb", ".xml", ".html", ".htm",
    ".fasta", ".fa", ".fna", ".faa", ".ffn", ".fastq", ".fq", ".gb", ".gbk", ".genbank", ".pdb", ".vcf",
    ".gff", ".gff3", ".gtf", ".bed", ".sam", ".yaml", ".yml", ".ini", ".cfg", ".log", ".tex", ".rst",
}
DOCUMENT_EXTENSIONS = TEXT_EXTENSIONS | {".pdf", ".docx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024


class DocumentError(ValueError):
    pass


def extract_text(data: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if len(data) > MAX_DOCUMENT_BYTES:
        raise DocumentError("File is larger than 25 MB.")
    if ext == ".pdf":
        return _pdf(data)
    if ext == ".docx":
        return _docx(data)
    if ext in TEXT_EXTENSIONS or not ext:
        text = _decode(data)
        if ext in {".html", ".htm", ".xml"}:
            text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", text, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
        if ext == ".ipynb":
            text = _notebook(text)
        if ext in {".csv", ".tsv"}:
            text = _table_preview(text, "\t" if ext == ".tsv" else ",") + "\n\n" + text
        return _normalise(text)
    raise DocumentError(f"Unsupported document type '{ext}'.")


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\x00", "")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise DocumentError("PDF support needs `pip install pypdf`.") from exc
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # malformed page; keep going
            text = ""
        if text.strip():
            pages.append(f"[Page {i + 1}]\n{text}")
    if not pages:
        raise DocumentError("No extractable text in this PDF (it may be a scanned image).")
    return _normalise("\n\n".join(pages))


def _docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise DocumentError("DOCX support needs `pip install python-docx`.") from exc
    document = docx.Document(io.BytesIO(data))
    parts = []
    for p in document.paragraphs:
        if not p.text.strip():
            continue
        style = (p.style.name or "").lower() if p.style is not None else ""
        if style.startswith("heading"):
            level = "".join(ch for ch in style if ch.isdigit()) or "2"
            parts.append("#" * min(int(level), 4) + " " + p.text)
        else:
            parts.append(p.text)
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return _normalise("\n\n".join(parts))


def _notebook(text: str) -> str:
    try:
        nb = json.loads(text)
    except json.JSONDecodeError:
        return text
    cells = []
    for cell in nb.get("cells", []):
        src = "".join(cell.get("source", []))
        if cell.get("cell_type") == "code":
            cells.append(f"```python\n{src}\n```")
        else:
            cells.append(src)
    return "\n\n".join(cells)


def _table_preview(text: str, delimiter: str) -> str:
    rows = list(csv.reader(io.StringIO(text[:200_000]), delimiter=delimiter))
    if not rows:
        return ""
    header = rows[0]
    return f"Table with {len(rows) - 1} data rows and {len(header)} columns: {', '.join(header[:30])}"


def chunk_text(text: str, target: int = 900, overlap: int = 150) -> list[dict]:
    """Split text into chunks, respecting Markdown headings where present.

    Returns [{"heading": str, "text": str}]
    """
    sections: list[tuple[str, str]] = []
    heading, buf = "", []
    for line in text.splitlines():
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            if "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))

    chunks: list[dict] = []
    for head, body in sections:
        if len(body) <= target * 1.3:
            chunks.append({"heading": head, "text": body})
            continue
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        current = ""
        for para in paragraphs:
            while len(para) > target * 1.5:  # very long paragraph: split near a sentence end
                cut = para.rfind(". ", target // 2, target)
                cut = cut + 1 if cut != -1 else target
                piece = para[:cut]
                para = para[cut - overlap:] if cut > overlap else para[cut:]
                chunks.append({"heading": head, "text": (current + "\n\n" + piece).strip()})
                current = ""
            if len(current) + len(para) > target and current:
                chunks.append({"heading": head, "text": current.strip()})
                current = current[-overlap:] + "\n\n" + para if overlap else para
            else:
                current = (current + "\n\n" + para) if current else para
        if current.strip():
            chunks.append({"heading": head, "text": current.strip()})
    return chunks
