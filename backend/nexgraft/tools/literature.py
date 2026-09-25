"""Literature search through the public Europe PMC REST API.

Europe PMC indexes PubMed/MEDLINE, PubMed Central and more. No API key is
needed. Requires an internet connection; everything else in NEXGRAFT runs
offline, so failures here are reported and the answer continues without it.
"""

from __future__ import annotations

import html
import re
from datetime import date
from typing import Any

import httpx

from .base import Param, ToolInputError, ToolSpec, result

EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

_STOPWORDS = {
    "a", "an", "and", "are", "about", "as", "at", "be", "by", "can", "could", "do", "does", "explain", "find",
    "for", "from", "give", "help", "how", "i", "in", "into", "is", "it", "latest", "me", "my", "new", "of",
    "on", "or", "please", "recent", "research", "show", "studies", "study", "summarize", "summarise", "tell",
    "the", "their", "this", "to", "understand", "want", "what", "which", "with", "would", "you", "your",
    "papers", "paper", "literature", "evidence", "related", "regarding", "current", "some", "should",
}
_RECENT_RE = re.compile(r"\b(recent|latest|new|current|emerging|state[- ]of[- ]the[- ]art)\b", re.I)


def keywords_from_text(text: str, limit: int = 8) -> str:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]+", text)
    keep: list[str] = []
    for w in words:
        lw = w.lower()
        if lw in _STOPWORDS or len(lw) < 3 or lw in (k.lower() for k in keep):
            continue
        keep.append(w)
    return " ".join(keep[:limit])


def _clean(text: str | None) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _record(r: dict[str, Any]) -> dict[str, Any]:
    source, rid, pmid = r.get("source"), r.get("id"), r.get("pmid")
    journal = ((r.get("journalInfo") or {}).get("journal") or {}).get("title") or r.get("bookOrReportDetails", {}).get("publisher", "")
    url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else f"https://europepmc.org/article/{source}/{rid}"
    authors = r.get("authorString") or ""
    if len(authors) > 90:
        authors = authors[:90].rsplit(",", 1)[0] + " et al."
    return {
        "kind": "literature",
        "title": _clean(r.get("title")).rstrip("."),
        "authors": authors,
        "journal": journal,
        "year": r.get("pubYear"),
        "pmid": pmid,
        "doi": r.get("doi"),
        "url": url,
        "open_access": r.get("isOpenAccess") == "Y",
        "cited_by": int(r.get("citedByCount") or 0),
        "abstract": _clean(r.get("abstractText")),
        "database": "Europe PMC",
    }


async def search_europe_pmc(query: str, limit: int = 5, recent: bool | None = None, timeout: float = 12.0) -> list[dict[str, Any]]:
    terms = keywords_from_text(query) or query.strip()
    if not terms:
        return []
    if recent is None:
        recent = bool(_RECENT_RE.search(query))
    filters = " AND HAS_ABSTRACT:y AND NOT SRC:PPR"
    if recent:
        filters += f" AND FIRST_PDATE:[{date.today().year - 5}-01-01 TO 2100-12-31]"
    attempts = [f"({terms}){filters}"]
    words = terms.split()
    if len(words) > 2:
        # fall back to requiring fewer terms if the strict AND query finds nothing
        attempts.append(f"({' '.join(words[:3])}){filters}")
        attempts.append(f"({' OR '.join(words)}){filters}")
    async with httpx.AsyncClient(timeout=timeout) as client:
        for q in attempts:
            r = await client.get(
                EUROPE_PMC,
                params={"query": q, "format": "json", "resultType": "core", "pageSize": limit},
            )
            r.raise_for_status()
            items = (r.json().get("resultList") or {}).get("result") or []
            if items:
                return [_record(i) for i in items[:limit]]
    return []


async def literature_tool(query: str, limit: float = 5, recent_only: bool = False) -> dict:
    if not query.strip():
        raise ToolInputError("Enter a search query.")
    try:
        records = await search_europe_pmc(query, int(limit), recent=recent_only or None)
    except httpx.HTTPError as exc:
        raise ToolInputError(f"Europe PMC could not be reached ({exc.__class__.__name__}). Check your internet connection.") from exc
    rows = [(f"[{i + 1}] {r['year'] or ''}", r["title"], "") for i, r in enumerate(records)]
    return result(f"{len(records)} article(s) from Europe PMC for “{keywords_from_text(query) or query}”", rows, sources=records)


TOOLS = [
    ToolSpec(
        id="literature_search",
        name="Literature search (Europe PMC)",
        description="Search peer-reviewed biomedical literature (PubMed/MEDLINE, PMC) with abstracts. Needs internet.",
        agent="medical",
        category="Literature",
        requires_network=True,
        params=[
            Param("query", "Search query", type="string", help="Keywords work best, e.g. 'wearable ECG atrial fibrillation'"),
            Param("limit", "Results", default=5, min=1, max=20),
            Param("recent_only", "Last 5 years only", type="boolean", default=False, required=False),
        ],
        run=literature_tool,
    ),
]
