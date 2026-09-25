"""Shared grounding helpers used by workspace preparation hooks."""

from __future__ import annotations

from ..knowledge.store import knowledge_base
from .base import Preparation, TaskContext


def retrieval_query(ctx: TaskContext) -> str:
    parts = [ctx.instruction]
    if ctx.message not in ctx.instruction:
        parts.append(ctx.message)
    if ctx.search_query:
        parts.append(ctx.search_query)
    return "\n".join(p for p in parts if p)[:2000]


async def add_knowledge(ctx: TaskContext, prep: Preparation, collections: list[str], k: int = 4) -> None:
    """Retrieve relevant chunks from the local knowledge base (RAG)."""
    if ctx.options.get("use_knowledge") is False:
        return
    hits = await knowledge_base.search(retrieval_query(ctx), collections, k=k)
    for chunk, score in hits:
        source = chunk.public(score)
        source["_text"] = f"{chunk.title} — {chunk.heading}\n{chunk.text}" if chunk.heading else f"{chunk.title}\n{chunk.text}"
        prep.sources.append(source)
