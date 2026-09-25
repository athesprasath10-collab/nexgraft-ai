# Demo script — NEXGRAFT AI local prototype (≈ 8 minutes)

A walkthrough for presenting the prototype to an incubation or review committee. Everything shown runs on the laptop.

## Before the demo (5 minutes)

1. Plug in the charger and set Windows to *Best performance*.
2. Start the Ollama app, then `start.bat`. Open **System & capabilities** and check:
   - Ollama connected and default model loaded (`qwen2.5:3b` recommended)
   - Embeddings: `nomic-embed-text` (semantic RAG enabled)
3. Send one warm-up message, e.g. "hello" in General AI, so the model is already in VRAM.
4. Optional: connect to the internet for the Europe PMC literature search, and use Chrome for voice input.

## 1. The problem and the idea (1 min) — Home page

> "Today a student or researcher uses one AI for general questions, another tool for literature, another environment for bioinformatics and separate tools for engineering. NEXGRAFT is one workspace where an orchestration layer finds the right expertise for each part of a problem."

Point to the orbit (four specialised workspaces around one orchestrator), the tagline and the four input options: Text, Voice, Image, Document.

## 2. Intelligent routing (1.5 min)

1. Type **"Explain Newton's laws."** Show that the analysis activates **only General AI**. Not every query activates every agent.
2. Start a new task and click the example card **"Generate Python code to analyze a DNA sequence and calculate GC content."** It routes to **Bioinformatics AI**.

Point out the pipeline stages (input understanding → problem analysis → task decomposition → routing) and the badge showing which router decided (LLM analyzer vs keyword fallback).

## 3. Multi-agent task graph (2 min)

Click the multi-agent example: *"I want to develop a wearable device for monitoring physiological parameters, and I also want to understand the relevant biological data."*

- Show the **detected domain**, required capabilities, recommended workspaces and the **dynamic task graph**.
- **User control:** toggle a workspace off or add one, then press **Proceed**.
- As each workspace streams its answer, show its sources (literature and knowledge base), the tool cards marked **computed**, and the tokens/s stats running on the GTX 1650 Ti.
- Finish on the **Unified output** card.

## 4. Specialised workspaces (2.5 min)

- **Bioinformatics AI:** paste a FASTA sequence and ask for an analysis script. The sequence toolkit computes exact values. In the **Code & workflow** panel, press **Run locally** → confirm → show the console output and plot. Say: *"The AI writes it, I review it, I choose to run it."* External tools like docking stay user-controlled.
- **Medical Research AI:** ask *"Explain recent research on diabetes biomarkers."* Show the Europe PMC citations [1], [2]… and the **Sources** panel. State the boundary: research, not diagnosis.
- **Hardware Design AI:** select the **Biomedical Engineering** plugin, run the *Wearable battery life* calculator, click **Use in prompt**, and ask for a power design. The answer builds on the verified numbers.

## 5. Multilingual and multimodal (0.5 min)

Set the language to **தமிழ் (Tamil)** or **हिन्दी (Hindi)** and ask a question, or use the mic. Attach a PDF paper and ask for a summary.

## 6. Honest scope and what the hardware unlocks (0.5 min)

Open **System & capabilities → Implemented vs roadmap** and the live **LangGraph structure**.

> "Everything on the left runs today on a 4 GB laptop GPU with 3B-parameter open models. Better hardware lets us run 7B–32B models, which reason better and handle Indian languages better, run agents in parallel, and add offline speech and larger knowledge bases."

## Likely questions

- **"Is this your own model?"** No. NEXGRAFT is the orchestration, specialisation and integration layer on top of open models (Qwen via Ollama). A proprietary model is not part of the prototype.
- **"Does it diagnose patients?"** No. The Medical workspace is for research and information discovery, and says so in its answers.
- **"Can it run docking or fabricate designs?"** It prepares workflows, scripts, parameters and calculations. The user runs external tools and does validation.
- **"Why sequential agents?"** A 4 GB GPU serves one model request at a time. The graph can run tasks in parallel on bigger hardware.
