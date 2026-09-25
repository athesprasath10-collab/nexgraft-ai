from __future__ import annotations

from .base import AgentSpec, Preparation, TaskContext
from .grounding import add_knowledge


async def prepare(ctx: TaskContext) -> Preparation:
    prep = Preparation()
    await add_knowledge(ctx, prep, ["general"], k=3)
    return prep


AGENT = AgentSpec(
    id="general",
    name="General AI",
    short_name="General",
    tagline="Reasoning, planning, writing and everyday problem solving",
    description="The common-purpose workspace for questions, explanations, planning, writing, brainstorming, coding and summarisation.",
    color="#8b7cff",
    icon="sparkles",
    workspace="chat",
    order=1,
    system_prompt=(
        "You are NEXGRAFT General AI, the general-purpose workspace. You help with explanations, reasoning, "
        "planning, writing, brainstorming, coding, summarisation and productivity. Give clear, well-structured "
        "answers: short for simple questions, thorough with headings, lists, tables and code blocks for complex ones. "
        "When planning projects, give concrete phases, milestones and deliverables."
    ),
    capabilities=["Reasoning", "Planning", "Writing", "Brainstorming", "Coding", "Summarisation", "General knowledge"],
    keywords={
        "plan": 1.5, "planning": 1.5, "roadmap": 1.5, "timeline": 1.2, "milestone": 1.2, "project": 1.0,
        "explain": 0.6, "summarize": 1.5, "summarise": 1.5, "summary": 1.2, "write": 1.2, "essay": 2.0,
        "email": 2.0, "letter": 1.5, "brainstorm": 2.0, "idea": 0.8, "ideas": 1.0, "translate": 1.2,
        "code": 0.8, "javascript": 1.5, "react": 1.2, "website": 1.2, "sql": 1.5, "algorithm": 1.2,
        "physics": 1.5, "newton": 2.0, "math": 1.5, "mathematics": 1.5, "history": 1.5, "resume": 2.0,
        "presentation": 1.5, "report": 0.8, "study plan": 2.0, "startup": 1.2, "business": 1.2,
        "pitch": 1.2, "marketing": 1.5, "productivity": 1.5, "schedule": 1.2,
    },
    knowledge_collections=["general"],
    user_controls=["Final decisions and how the output is used"],
    examples=[
        "I have a college project idea. Help me create a development plan.",
        "Explain Newton's laws of motion with everyday examples.",
        "Write a one-page proposal for an AI incubation grant.",
    ],
    prepare=prepare,
    subtask_title="Project planning & overview",
    subtask_instruction="Create a concise structured plan (phases, milestones, deliverables) and explain how the parts of this request fit together: {message}",
)
