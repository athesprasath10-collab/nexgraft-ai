from __future__ import annotations

import httpx

from ..config import settings
from ..tools.literature import search_europe_pmc
from .base import AgentSpec, Preparation, TaskContext
from .grounding import add_knowledge


async def prepare(ctx: TaskContext) -> Preparation:
    prep = Preparation()
    use_literature = ctx.options.get("literature", settings.literature_search)
    if use_literature:
        query = ctx.search_query or ctx.instruction or ctx.message
        try:
            records = await search_europe_pmc(query, limit=int(ctx.options.get("literature_limit", 5)))
            prep.tool_calls.append({
                "tool": "literature_search",
                "name": "Literature search (Europe PMC)",
                "input": {"query": query},
                "output": {"summary": f"{len(records)} article(s) with abstracts", "results": []},
            })
            for rec in records:
                abstract = rec["abstract"]
                if len(abstract) > 1100:
                    abstract = abstract[:1100].rsplit(" ", 1)[0] + "…"
                rec = {**rec, "snippet": abstract[:400] + ("…" if len(abstract) > 400 else "")}
                rec["_text"] = (
                    f"{rec['title']} ({rec['authors']}; {rec['journal']}, {rec['year']}). "
                    f"Abstract: {abstract}"
                )
                rec.pop("abstract", None)
                prep.sources.append(rec)
            if not records:
                prep.notes.append("Literature search returned no matching articles; answer uses the local knowledge base and model knowledge.")
        except httpx.HTTPError as exc:
            prep.notes.append(f"Literature search unavailable ({exc.__class__.__name__}) — working offline with local knowledge only.")
    await add_knowledge(ctx, prep, ["medical"], k=3)
    return prep


AGENT = AgentSpec(
    id="medical",
    name="Medical & Healthcare Research AI",
    short_name="Medical Research",
    tagline="Research-grade literature exploration and evidence synthesis",
    description="A research workspace for medical, healthcare and biomedical questions: literature exploration, evidence-oriented synthesis and scientific knowledge. Not a diagnostic or telemedicine system.",
    color="#4cc9f0",
    icon="microscope",
    workspace="research",
    order=3,
    system_prompt=(
        "You are NEXGRAFT Medical & Healthcare Research AI, a research assistant for medical, healthcare and biomedical "
        "research: literature exploration, evidence synthesis, study design, physiology, biomarkers and health technology.\n"
        "You are NOT a diagnostic, prescribing or telemedicine system. Do not diagnose or give personal treatment advice. "
        "If someone asks about their own symptoms or treatment, say briefly that you provide research information and "
        "that they should consult a qualified clinician, then give research-oriented information.\n"
        "Structure answers as: ## Research question, ## Key findings, ## Evidence & sources, ## Synthesis, "
        "## Limitations & gaps.\n"
        "When numbered sources are provided, ground specific claims in them and cite like [1] or [2]. Never invent "
        "references, authors, DOIs or statistics. Mark statements that come from general knowledge rather than the sources."
    ),
    capabilities=["Literature search (Europe PMC)", "Evidence synthesis", "Study design & appraisal", "Physiology & biomarkers", "Health technology research"],
    keywords={
        "medical": 2.5, "medicine": 2.0, "clinical": 2.5, "clinical trial": 3.0, "healthcare": 2.5, "health": 1.2,
        "disease": 2.5, "diseases": 2.5, "disorder": 2.0, "syndrome": 2.0, "diabetes": 3.0, "cancer": 3.0,
        "tumor": 2.5, "tumour": 2.5, "cardiac": 2.0, "cardiovascular": 2.5, "heart": 1.5, "hypertension": 3.0,
        "biomarker": 3.0, "biomarkers": 3.0, "patient": 2.0, "patients": 2.0, "treatment": 2.0, "therapy": 2.0,
        "drug": 1.5, "vaccine": 2.5, "epidemiology": 3.0, "prevalence": 2.5, "mortality": 2.5, "physiology": 2.0,
        "physiological": 1.5, "pathology": 2.5, "literature": 2.0, "research": 1.0, "study": 0.6, "studies": 1.0,
        "evidence": 1.5, "meta-analysis": 3.0, "systematic review": 3.0, "pubmed": 3.0, "infection": 2.5,
        "alzheimer": 3.0, "parkinson": 3.0, "stroke": 2.5, "covid": 3.0, "asthma": 3.0, "obesity": 2.5,
        "blood pressure": 2.0, "glucose": 2.0, "arrhythmia": 3.0, "atrial fibrillation": 3.0, "ecg": 1.0,
        "symptom": 2.0, "symptoms": 2.0, "diagnosis": 1.5, "medical research": 3.5,
        "physiological parameters": 2.0, "vital signs": 2.5, "cardiac parameters": 1.5,
    },
    knowledge_collections=["medical"],
    user_controls=["Clinical interpretation and any healthcare decisions (by qualified professionals)", "Choosing and reading the underlying studies"],
    examples=[
        "Find and summarize research about wearable monitoring of cardiac parameters.",
        "Explain recent research on diabetes biomarkers.",
        "What does the evidence say about PPG-based atrial fibrillation screening?",
    ],
    tools=["literature_search"],
    prepare=prepare,
    subtask_title="Medical & healthcare research",
    subtask_instruction="Summarise the relevant medical and healthcare research, key parameters and evidence for this request: {message}",
    temperature=0.3,
    boundary="Assists research and information discovery. It does not diagnose, prescribe or provide telemedicine.",
)
