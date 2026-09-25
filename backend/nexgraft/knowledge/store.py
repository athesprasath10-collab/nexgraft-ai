"""Local knowledge base: hybrid retrieval over domain collections.

* Each sub-folder of `knowledge/` is a collection (general, bioinformatics,
  medical, hardware-electronics, …). Drop files in and re-index.
* Keyword retrieval (BM25) always works offline with no extra models.
* Semantic retrieval uses an Ollama embedding model (default
  `nomic-embed-text`) and a local on-disk vector index (NumPy). If the
  embedding model is not installed, retrieval falls back to BM25 only.
* Results from both are merged with reciprocal-rank fusion.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from ..config import settings
from ..llm.ollama import OllamaClient, OllamaError, ollama
from ..multimodal.documents import DOCUMENT_EXTENSIONS, DocumentError, chunk_text, extract_text

log = logging.getLogger("nexgraft.knowledge")

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
STOPWORDS = {
    "a", "about", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can", "could", "do", "does",
    "explain", "for", "from", "give", "has", "have", "help", "how", "i", "if", "in", "into", "is", "it", "its",
    "me", "my", "of", "on", "or", "our", "please", "should", "so", "some", "tell", "than", "that", "the",
    "their", "them", "then", "there", "these", "they", "this", "to", "up", "us", "use", "want", "was", "we",
    "what", "when", "where", "which", "while", "who", "why", "will", "with", "would", "you", "your",
}


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in _TOKEN_RE.findall(text.lower()):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return tokens


@dataclass
class Chunk:
    id: str
    collection: str
    doc: str
    title: str
    heading: str
    text: str
    tokens: list[str] = field(default_factory=list, repr=False)

    def public(self, score: float | None = None) -> dict[str, Any]:
        snippet = self.text if len(self.text) <= 420 else self.text[:420].rsplit(" ", 1)[0] + "…"
        return {
            "kind": "knowledge",
            "collection": self.collection,
            "doc": self.doc,
            "title": self.title,
            "heading": self.heading,
            "snippet": snippet,
            "score": round(score, 3) if score is not None else None,
        }


@dataclass
class Collection:
    id: str
    chunks: list[Chunk] = field(default_factory=list)
    vectors: np.ndarray | None = None
    embed_model: str | None = None
    docs: list[dict[str, Any]] = field(default_factory=list)
    indexed_at: float = 0.0


def _doc_title(text: str, path: Path) -> str:
    m = re.search(r"^#\s+(.+)$", text, flags=re.M)
    return m.group(1).strip() if m else path.stem.replace("-", " ").replace("_", " ").title()


class KnowledgeBase:
    def __init__(self, root: Path, index_dir: Path, client: OllamaClient) -> None:
        self.root = root
        self.index_dir = index_dir
        self.client = client
        self.collections: dict[str, Collection] = {}
        self._lock = asyncio.Lock()
        self.embeddings_available = False
        self.status = "not indexed"
        self.last_error: str | None = None

    # ---------------------------------------------------------------- indexing
    def collection_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir() and not p.name.startswith("."))

    def _files(self, cid: str) -> list[Path]:
        folder = self.root / cid
        return sorted(
            p for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in DOCUMENT_EXTENSIONS and not p.name.startswith(".")
        )

    def _signature(self, files: list[Path]) -> str:
        h = hashlib.sha1()
        for f in files:
            st = f.stat()
            h.update(f"{f.relative_to(self.root)}:{st.st_size}:{int(st.st_mtime)}".encode())
        return h.hexdigest()

    async def build(self, only: str | None = None, force: bool = False) -> None:
        async with self._lock:
            self.status = "indexing"
            self.embeddings_available = await self.client.has_model(settings.embed_model)
            for cid in self.collection_ids():
                if only and cid != only:
                    continue
                try:
                    self.collections[cid] = await self._build_collection(cid, force)
                except Exception as exc:  # keep other collections usable
                    log.exception("Indexing %s failed", cid)
                    self.last_error = f"{cid}: {exc}"
            # drop collections whose folder was removed
            for cid in list(self.collections):
                if cid not in self.collection_ids():
                    del self.collections[cid]
            self.status = "ready"

    async def _build_collection(self, cid: str, force: bool) -> Collection:
        files = self._files(cid)
        signature = self._signature(files)
        embed_model = settings.embed_model if self.embeddings_available else None
        cache = self.index_dir / cid
        meta_path, vec_path = cache / "chunks.json", cache / "vectors.npy"

        if not force and meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("signature") == signature and (meta.get("embed_model") == embed_model or embed_model is None):
                col = Collection(id=cid, docs=meta["docs"], indexed_at=meta.get("indexed_at", 0))
                col.chunks = [Chunk(**c, tokens=tokenize(f"{c['title']} {c['heading']} {c['text']}")) for c in meta["chunks"]]
                if meta.get("embed_model") and vec_path.is_file() and embed_model:
                    col.vectors = np.load(vec_path)
                    col.embed_model = meta["embed_model"]
                return col

        col = Collection(id=cid, indexed_at=time.time())
        for path in files:
            try:
                text = extract_text(path.read_bytes(), path.name)
            except DocumentError as exc:
                col.docs.append({"file": path.name, "title": path.name, "chunks": 0, "error": str(exc)})
                continue
            title = _doc_title(text, path)
            pieces = chunk_text(text)
            rel = str(path.relative_to(self.root / cid)).replace("\\", "/")
            for i, piece in enumerate(pieces):
                col.chunks.append(
                    Chunk(
                        id=f"{cid}/{rel}#{i}",
                        collection=cid,
                        doc=rel,
                        title=title,
                        heading=piece["heading"],
                        text=piece["text"],
                        tokens=tokenize(f"{title} {piece['heading']} {piece['text']}"),
                    )
                )
            col.docs.append({"file": rel, "title": title, "chunks": len(pieces), "size": path.stat().st_size})

        if embed_model and col.chunks:
            try:
                col.vectors = await self._embed_documents([f"{c.title} — {c.heading}\n{c.text}" for c in col.chunks])
                col.embed_model = embed_model
            except OllamaError as exc:
                self.last_error = str(exc)
                col.vectors = None

        cache.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps(
                {
                    "signature": signature,
                    "embed_model": col.embed_model,
                    "indexed_at": col.indexed_at,
                    "docs": col.docs,
                    "chunks": [
                        {k: getattr(c, k) for k in ("id", "collection", "doc", "title", "heading", "text")}
                        for c in col.chunks
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if col.vectors is not None:
            np.save(vec_path, col.vectors)
        elif vec_path.exists():
            vec_path.unlink()
        return col

    def _prefix(self, kind: str) -> str:
        # nomic-embed-text is trained with task prefixes
        if "nomic" in settings.embed_model:
            return "search_query: " if kind == "query" else "search_document: "
        return ""

    async def _embed_documents(self, texts: list[str]) -> np.ndarray:
        vectors: list[list[float]] = []
        prefix = self._prefix("doc")
        for i in range(0, len(texts), 16):
            batch = [prefix + t[:2000] for t in texts[i:i + 16]]
            vectors.extend(await self.client.embed(settings.embed_model, batch))
        return _normalise(np.asarray(vectors, dtype=np.float32))

    async def _embed_query(self, text: str) -> np.ndarray | None:
        try:
            vec = await self.client.embed(settings.embed_model, [self._prefix("query") + text[:2000]])
        except OllamaError:
            return None
        return _normalise(np.asarray(vec, dtype=np.float32))[0] if vec else None

    # --------------------------------------------------------------- retrieval
    @property
    def mode(self) -> str:
        has_vectors = any(c.vectors is not None for c in self.collections.values())
        return "hybrid" if has_vectors else "keyword"

    async def search(
        self,
        query: str,
        collections: list[str],
        k: int = 4,
        min_bm25: float = 2.5,
        min_cosine: float = 0.62,
    ) -> list[tuple[Chunk, float]]:
        cols = [self.collections[c] for c in collections if c in self.collections]
        chunks = [ch for col in cols for ch in col.chunks]
        if not chunks or not query.strip():
            return []

        bm25 = bm25_scores(tokenize(query), [c.tokens for c in chunks])

        cosine = np.full(len(chunks), -1.0, dtype=np.float32)
        if any(col.vectors is not None for col in cols):
            qvec = await self._embed_query(query)
            if qvec is not None:
                offset = 0
                for col in cols:
                    n = len(col.chunks)
                    if col.vectors is not None and col.vectors.shape[0] == n and col.vectors.shape[1] == qvec.shape[0]:
                        cosine[offset:offset + n] = col.vectors @ qvec
                    offset += n

        rrf = np.zeros(len(chunks))
        for scores, floor in ((np.asarray(bm25), min_bm25), (cosine, min_cosine)):
            order = np.argsort(-scores)
            for rank, idx in enumerate(order[: max(k * 4, 10)]):
                if scores[idx] >= floor:
                    rrf[idx] += 1.0 / (60 + rank)
        picked = [int(i) for i in np.argsort(-rrf) if rrf[i] > 0][:k]
        return [(chunks[i], float(max(cosine[i], 0.0)) if cosine[i] >= 0 else float(bm25[i])) for i in picked]

    def search_chunks(self, query: str, chunks: list[dict[str, str]], k: int = 4) -> list[int]:
        """BM25 ranking over ad-hoc chunks (used for attached documents)."""
        scores = bm25_scores(tokenize(query), [tokenize(c["text"]) for c in chunks])
        order = sorted(range(len(chunks)), key=lambda i: -scores[i])
        return order[:k]

    # ----------------------------------------------------------------- listing
    def stats(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "mode": self.mode,
            "embed_model": settings.embed_model,
            "embeddings_available": self.embeddings_available,
            "last_error": self.last_error,
            "collections": [
                {
                    "id": cid,
                    "documents": col.docs,
                    "chunks": len(col.chunks),
                    "vectors": col.vectors is not None,
                    "indexed_at": col.indexed_at,
                }
                for cid, col in sorted(self.collections.items())
            ],
        }


def bm25_scores(query: list[str], docs: list[list[str]], k1: float = 1.4, b: float = 0.75) -> list[float]:
    if not docs or not query:
        return [0.0] * len(docs)
    n = len(docs)
    avgdl = sum(len(d) for d in docs) / n or 1.0
    df: Counter[str] = Counter()
    for d in docs:
        df.update(set(d))
    q_terms = set(query)
    scores = []
    for d in docs:
        tf = Counter(t for t in d if t in q_terms)
        dl = len(d) or 1
        s = 0.0
        for term, f in tf.items():
            idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


def _normalise(m: np.ndarray) -> np.ndarray:
    if m.ndim == 1:
        m = m[None, :]
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return m / norms


knowledge_base = KnowledgeBase(settings.knowledge_dir, settings.index_dir, ollama)
