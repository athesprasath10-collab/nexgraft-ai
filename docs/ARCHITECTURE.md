# NEXGRAFT architecture (local prototype)

This document describes what the code does today. Roadmap items are marked as such.

## Components

```
Browser (React)                     Python backend (FastAPI)                      Local services
────────────────                    ─────────────────────────                     ──────────────
Orchestrator / workspaces  ──POST /api/analyze──▶  LangGraph analysis graph ─────▶ Ollama (Qwen, JSON schema)
  plan review & editing    ◀──── NDJSON stream ─┘
                           ──POST /api/run──────▶  LangGraph execution graph ────▶ Ollama (streaming chat)
  streaming results        ◀──── NDJSON stream ─┘      │  prepare hooks ────────▶ Knowledge base (BM25 + vectors)
Tool panels                ──POST /api/tools/{id}─▶ deterministic tools            ├▶ Ollama embeddings
Code panel "Run locally"   ──POST /api/execute──▶  subprocess runner               └▶ Europe PMC (internet)
Composer uploads           ──POST /api/attachments▶ text extraction / vision ─────▶ Ollama vision model
Knowledge / System pages   ──GET  /api/knowledge, /api/status, /api/graph, /api/config
```

## Orchestration graphs (LangGraph)

**Analysis graph** — `backend/nexgraft/orchestrator/graph.py`

1. `understand_input` — detects the response language from the script (Tamil, Hindi, Telugu…), counts attached documents and images, detects biological sequences, and resolves the chat model.
2. `analyze_problem` — asks the local model for a plan using Ollama structured outputs (a JSON schema whose `workspace` field is an enum of the registered agents). The prompt lists each workspace's description and capabilities and a few examples. If the model errors or exceeds `NEXGRAFT_ANALYZER_TIMEOUT`, the keyword router (`heuristics.py`) produces the plan. When the prompt is in English, a guard fixes two common small-model mistakes: sending a strongly bioinformatics, medical or hardware request only to General AI, and adding workspaces the request gives no reason for.
3. `decompose_tasks` — normalises the tasks (at most one per workspace, up to four) and marks the plan as single- or multi-agent.
4. `route_agents` — attaches workspace metadata and the engineering domain plugin, then emits the `analysis` event.

**Execution graph**

1. `start` → `run_task` (a conditional edge loops once per task) → `synthesize` (only for multi-task plans with synthesis on).
2. `run_task` calls the workspace's `prepare` hook (retrieval + tools), builds the prompt within a character budget derived from `num_ctx` (history, attachments, sources, tool results), and streams tokens from Ollama.
3. `synthesize` writes a short unified summary, "how the pieces fit" and user-controlled next steps.

Nodes emit progress through LangGraph's custom stream writer. The server forwards them as newline-delimited JSON.

## Stream events

| Event | Meaning |
|---|---|
| `stage` | Analysis node progress: `{stage, status: active\|done, label, detail}` |
| `analysis` | Final plan: domain, intent, capabilities, tasks, router used, notes, language, signals |
| `run_start` | Tasks about to execute |
| `task_start` / `task_phase` | A task begins; phase `grounding` then `generating` (with model) |
| `tool` | A tool result used for grounding (e.g. `sequence_stats`, `literature_search`) |
| `sources` | Numbered sources for citations (knowledge chunks, literature records) |
| `note` | Non-fatal notice (e.g. literature search offline) |
| `token` | Streamed text for a task (`task_id` = `t1…` or `synthesis`) |
| `task_end` | Stats: model, tokens/s, token counts, seconds, stop reason |
| `task_error` / `error` | Failures, with user-readable messages |
| `done` | Stream finished |

## Workspaces, plugins and tools

- `agents/*.py`: each module exposes `AGENT = AgentSpec(...)`: system prompt, routing keywords, knowledge collections, user-control statements, examples, tools and an optional async `prepare(ctx) -> Preparation` hook.
  - General: retrieves from the `general` collection.
  - Bioinformatics: finds sequences in the message or attached FASTA files, runs `sequence_stats`, and injects the results as verified values. Retrieves from `bioinformatics`.
  - Medical: Europe PMC search (abstracts become numbered sources) plus the `medical` collection.
  - Hardware: draws a circuit schematic when the request is about one (below), then retrieves from the active plugin's collection first and the other engineering collections after it.
- `plugins/hardware/*.py`: `PLUGIN = PluginSpec(...)` with keywords (plugin detection), a prompt add-on, a knowledge collection and calculators.
- `tools/*.py`: `ToolSpec` with a typed parameter list; `coerce()` validates input (number fields accept `10k`, `4k7`, `100 nF`, `20 mA`), and results use a standard `{summary, results[], warnings, notes}` shape. Calculators with `schematic=True` also return `schematic {svg, title, caption}` and `parts [{ref, value, description}]`.

### Circuit schematics

`agents/schematic.py` runs in the Hardware `prepare` hook. A regex gate skips requests without circuit words, and requests for circuits no calculator draws (buck, boost, 555, H-bridge…) skip the step entirely. Otherwise one JSON-schema call to the default model returns `{circuit, values}`. The schema has one `anyOf` branch per circuit, so the model only sees that circuit's parameters, and choice parameters are enums. Then:

1. A keyword guard drops a pick that does not match the request (e.g. a regulator for "control a lamp").
2. Each value is parsed with its unit. A number the request does not state is kept only when it is a required voltage (common facts such as 3.3 V logic or a 2 V red LED) or a feature the request names (e.g. "debounce"); otherwise the calculator default applies. Kept model choices and defaults are listed in the result's first note.
3. The calculator computes E-series values and `tools/circuits.py` draws the fixed layout for that circuit with schemdraw's SVG backend, so wiring never depends on the model.

The result streams as a normal `tool` event (the UI shows the drawing, parts list and SVG/PNG download), and the model is told to explain the schematic by designator using the computed values. `options.diagrams = false` turns the step off.

## Knowledge layer

`knowledge/store.py` treats every folder in `knowledge/` as a collection. Files (MD, TXT, PDF, DOCX, CSV, FASTA…) are split into chunks by Markdown heading or paragraph. Search combines:

- **BM25** over tokenised chunks (always available, offline), and
- **cosine similarity** over embeddings from the Ollama model `nomic-embed-text` (with its `search_query:` / `search_document:` prefixes), stored as NumPy arrays in `data/index/<collection>/`.

Results are fused with reciprocal-rank fusion. Relevance floors keep unrelated chunks out, so "Explain Newton's laws" retrieves nothing. The index is rebuilt only when a collection's files change, or when the embedding model becomes available.

*Roadmap:* a dedicated vector database for large corpora.

## Multimodal and multilingual

- **Documents:** text is extracted on upload (`multimodal/documents.py`). Long documents contribute only the chunks most relevant to the task (BM25), within the context budget. The original files are also available to the code runner by name.
- **Images:** described by a local vision model (`qwen2.5vl`, `moondream`, …). The description then enters the pipeline like any other input.
- **Voice:** browser Web Speech API for input, with the selected language's BCP-47 tag (e.g. `ta-IN`), and speech synthesis for read-aloud. *Roadmap:* offline Whisper.
- **Languages:** the script is detected deterministically. Answers are requested in the user's language, with technical terms kept in English. The analyzer writes its instructions and search queries in English, so literature search still works.

## Performance choices for a 4 GB GPU

- Sequential agents; one resident chat model (`keep_alive`), with an embedding model small enough to sit alongside it.
- Thinking mode is disabled automatically for models that support it (e.g. Qwen3).
- Context and output limits are configurable; prompts are budgeted to `num_ctx`.
- The UI's 3D hero is a lightweight 2D projection (or an optional Spline scene), and the background is static.

## Security model

The server binds to `127.0.0.1`, rejects requests whose `Host` is not local (preventing DNS rebinding), and rejects cross-origin writes. The code runner is user-triggered, time-limited and isolated only by a temporary working directory. It is not a sandbox.
