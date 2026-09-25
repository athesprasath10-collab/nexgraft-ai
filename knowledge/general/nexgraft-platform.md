# NEXGRAFT AI platform overview

## What NEXGRAFT is
NEXGRAFT is a unified multi-domain AI workspace. Instead of switching between separate tools for general questions, bioinformatics, medical research and engineering, a user describes the problem once. An orchestration layer understands the request, identifies the domain and the capabilities it needs, breaks complex problems into tasks, and routes each task to the relevant specialised workspace. Tagline: One Platform. Multiple Experts. One Intelligent Solution.

## The four workspaces
- General AI: explanations, reasoning, planning, writing, brainstorming, coding, summarisation and productivity.
- Bioinformatics AI: sequence analysis, code and workflow generation, pipelines, and guidance for external tools such as BLAST or AutoDock Vina. The user runs external tools.
- Medical & Healthcare Research AI: medical, healthcare and biomedical research: literature exploration and evidence synthesis. It is not a diagnostic or telemedicine system.
- Hardware Design AI: engineering guidance through domain plugins (biomedical, electronics, mechanical, civil, electrical). The user controls design, simulation, fabrication and validation.

## Orchestration flow
Input understanding → problem and intent analysis → task decomposition → capability identification → agent routing → knowledge and tools → result generation → unified output. Simple requests use one workspace. Complex requests become a task graph where each task goes to the workspace with the right expertise. Not every request activates every agent.

## Principles
Right AI for the right problem. Modular, extensible, plugin-based, domain-specific and user-controlled. AI provides information, reasoning, code, workflows and design guidance. The user controls execution, experiments, fabrication, validation and final decisions.

## Local prototype stack
Python backend (FastAPI) with LangGraph orchestration, local LLMs served by Ollama (Qwen family), hybrid retrieval (BM25 plus a local vector index built with an Ollama embedding model), deterministic domain tools, and a React web interface.
