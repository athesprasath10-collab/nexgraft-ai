import { ArrowDown, CircleCheck, CircleDashed, Copy, Cpu, Eye, GitBranch, HardDrive, Layers, LoaderCircle, Menu, RefreshCw, Server, Sparkles } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { DynamicIcon, IconTile } from "../components/Icon";
import { toast } from "../components/Toast";
import { api } from "../lib/api";
import { useStore } from "../lib/store";
import type { GraphStructure } from "../lib/types";
import { copyText, cx, formatBytes } from "../lib/utils";

const IMPLEMENTED: [string, string][] = [
  ["Unified web workspace", "Orchestrator home plus four specialised workspaces in one React interface."],
  ["LangGraph orchestration", "Input understanding → LLM problem & intent analysis (JSON schema) → task decomposition → routing, with a keyword router fallback and guard."],
  ["Dynamic task graph", "Only the needed workspaces run; multi-part problems execute as a task graph with a unified synthesis. Tasks run sequentially on one local GPU."],
  ["Local LLMs via Ollama", "Qwen-family models on your GPU; optional per-workspace model."],
  ["Local fine-tuning", "Optional QLoRA fine-tunes of Qwen for Bioinformatics and Hardware Design on a 4 GB GPU, merged into the base weights and served by Ollama."],
  ["Knowledge layer (RAG)", "Hybrid retrieval: BM25 + a local NumPy vector index built with an Ollama embedding model, over domain collections you can extend."],
  ["Bioinformatics tools", "Sequence statistics, translation, ORF finder and Biopython alignment; generated scripts run locally only when you press Run."],
  ["Medical literature search", "Europe PMC (PubMed/MEDLINE, PMC) abstracts with numbered citations. Research only — no diagnosis."],
  ["Hardware domain plugins", "Biomedical, Electronics, Mechanical, Civil and Electrical plugins with deterministic engineering calculators."],
  ["Circuit schematics", "Eight common circuits (LED, divider, button, transistor switch, RC filter, two op-amp amplifiers, LDO) drawn with computed standard values, a parts list and SVG/PNG download; the model explains them."],
  ["Multimodal input", "Text; voice via browser speech recognition (Chrome/Edge); PDF, DOCX, text, CSV and FASTA documents; images through an optional local vision model."],
  ["Multilingual", "English + 10 Indian languages: script detection, language-matched answers and read-aloud. Quality depends on the model size."],
  ["Local & private", "Runs on this computer; conversations are stored in your browser."],
];

const ROADMAP: [string, string][] = [
  ["Offline speech", "Local speech-to-text (e.g. Whisper) and better Indic text-to-speech."],
  ["Bigger & parallel models", "Parallel agent execution and larger or fine-tuned models on incubation hardware."],
  ["More workspaces & plugins", "e.g. chemistry, data science, robotics and aerospace plugins."],
  ["Deeper tool integrations", "NCBI BLAST, UniProt/PDB retrieval, workflow managers, clinical-trial registries — with user approval."],
  ["Agentic tool-calling loops", "Multi-step tool use by agents, always with explicit user control."],
  ["Dedicated vector database", "Chroma/Qdrant-class storage for large document corpora."],
  ["Accounts & collaboration", "Shared projects and deployment beyond a single machine."],
  ["Proprietary NEXGRAFT models", "Not built today — the prototype uses open models through Ollama."],
];

function GraphFlow({ name, g }: { name: string; g: GraphStructure }) {
  const nodes = g.nodes.filter((n) => !n.startsWith("__"));
  const loops = g.edges.filter((e) => e.source === e.target).map((e) => e.source);
  const conditional = new Set(g.edges.filter((e) => e.conditional && e.source !== e.target).map((e) => `${e.source}>${e.target}`));
  return (
    <div className="graph-flow">
      <p className="nav-label">{name} graph</p>
      <div className="flow">
        <span className="flow-node terminal">START</span>
        {nodes.map((n, i) => (
          <div key={n} className="flow-step">
            <ArrowDown size={14} className={cx("flow-arrow", i > 0 && conditional.has(`${nodes[i - 1]}>${n}`) && "cond")} />
            <span className="flow-node">
              <span className="mono">{n}</span>
              {loops.includes(n) && <span className="tag">↺ once per task</span>}
            </span>
          </div>
        ))}
        <ArrowDown size={14} className="flow-arrow" />
        <span className="flow-node terminal">END</span>
      </div>
      <button
        className="btn btn-sm btn-ghost"
        onClick={async () => {
          if (await copyText(g.mermaid)) toast.success("Mermaid diagram copied");
        }}
      >
        <Copy size={13} /> Copy Mermaid
      </button>
    </div>
  );
}

export function SystemView() {
  const { status, setStatus, config, setSidebarOpen } = useStore();
  const [graph, setGraph] = useState<Record<string, GraphStructure> | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    api
      .status()
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, [setStatus]);

  useEffect(() => {
    refresh();
    api.graph().then(setGraph).catch(() => setGraph(null));
  }, [refresh]);

  const chatModels = (status?.models || []).filter((m) => !m.is_embedding);

  return (
    <div className="view scroll-area">
      <div className="page">
        <header className="page-head">
          <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div>
            <span className="eyebrow">
              <Server size={12} /> Runtime
            </span>
            <h1>System & capabilities</h1>
            <p className="muted">What is running on this machine, and a clear line between what this prototype does today and what is on the roadmap.</p>
          </div>
          <button className="btn btn-ghost" onClick={refresh} disabled={loading}>
            {loading ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />} Refresh
          </button>
        </header>

        <div className="stat-row">
          <div className={cx("stat-card", status?.ollama.reachable ? "good" : "bad")}>
            <span className="stat-k">
              <Cpu size={12} /> Ollama
            </span>
            <span className="stat-v">{status?.ollama.reachable ? `Connected · v${status.ollama.version}` : "Not reachable"}</span>
            <span className="faint small mono">{status?.ollama.url}</span>
          </div>
          <div className={cx("stat-card", status?.default_model ? "good" : "warn")}>
            <span className="stat-k">
              <Sparkles size={12} /> Default chat model
            </span>
            <span className="stat-v">{status?.default_model || "—"}</span>
            <span className="faint small">{status?.model_error || `${chatModels.length} chat model(s) installed`}</span>
          </div>
          <div className={cx("stat-card", status?.embed_model.installed ? "good" : "warn")}>
            <span className="stat-k">
              <Layers size={12} /> Embeddings
            </span>
            <span className="stat-v">{status?.embed_model.installed ? status.embed_model.name : "Keyword retrieval only"}</span>
            <span className="faint small">{status?.embed_model.installed ? "Semantic RAG enabled" : <code>ollama pull {status?.embed_model.name || "nomic-embed-text"}</code>}</span>
          </div>
          <div className={cx("stat-card", status?.vision_model ? "good" : "warn")}>
            <span className="stat-k">
              <Eye size={12} /> Vision
            </span>
            <span className="stat-v">{status?.vision_model || "No vision model"}</span>
            <span className="faint small">{status?.vision_model ? "Image input enabled" : <code>ollama pull qwen2.5vl:3b</code>}</span>
          </div>
        </div>

        <div className="two-col">
          <section className="panel-card">
            <h3>
              <HardDrive size={16} /> Loaded in memory
            </h3>
            {status?.running.length ? (
              status.running.map((r) => (
                <div key={r.name} className="vram-row">
                  <div className="vram-top">
                    <span className="mono">{r.name}</span>
                    <span className="faint small">
                      {formatBytes(r.size)} · ctx {r.context_length ?? "?"}
                    </span>
                  </div>
                  <div className="bar">
                    <span style={{ width: `${r.gpu_percent}%` }} />
                  </div>
                  <span className="faint small">
                    {r.gpu_percent}% on GPU ({formatBytes(r.size_vram)}){r.gpu_percent < 100 ? " — the rest runs on CPU (slower)" : ""}
                  </span>
                </div>
              ))
            ) : (
              <p className="faint small">No model loaded right now. Models load on the first request and unload after {status?.settings.keep_alive || "15m"} idle.</p>
            )}
            <h3 className="mt">Installed models</h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Size</th>
                  <th>Capabilities</th>
                </tr>
              </thead>
              <tbody>
                {status?.models.map((m) => (
                  <tr key={m.name}>
                    <td className="mono">{m.name}</td>
                    <td>{formatBytes(m.size)}</td>
                    <td>
                      {Object.entries(status?.finetuned_models || {})
                        .filter(([, name]) => name === m.name)
                        .map(([agent]) => (
                          <span key={agent} className="tag">
                            fine-tuned · {config?.agents.find((a) => a.id === agent)?.short_name || agent}
                          </span>
                        ))}
                      {m.capabilities.map((c) => (
                        <span key={c} className="tag">
                          {c}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="panel-card">
            <h3>
              <Cpu size={16} /> Tuned for a 4 GB GPU (e.g. GTX 1650 Ti)
            </h3>
            <ul className="tips">
              <li>
                <b>qwen2.5:3b</b> (~1.9 GB) fits fully in VRAM — the best speed/quality balance.
              </li>
              <li>
                <b>qwen3:4b</b> (~2.5 GB) is smarter; set context to 4096 in Settings. Thinking mode is disabled automatically for speed.
              </li>
              <li>
                <b>qwen2.5:7b</b> (~4.7 GB) works but part of it runs on the CPU — expect slower answers.
              </li>
              <li>
                Optional: <b>qwen2.5-coder:3b</b> as the Bioinformatics model, <b>nomic-embed-text</b> for semantic RAG, <b>qwen2.5vl:3b</b> or <b>moondream</b>{" "}
                for images (loaded on demand).
              </li>
              <li>
                Fine-tuned <b>nexgraft-bioinformatics</b> and <b>nexgraft-hardware</b> (~2.2 GB each) can be built on this GPU with <b>finetune.bat</b>; their
                workspaces then use them automatically.
              </li>
              <li>Agents run one after another so they never fight over VRAM. Turn off the 3D hero to give the GPU fully to the model.</li>
            </ul>
          </section>
        </div>

        <section className="panel-card">
          <h3>
            <CircleCheck size={16} /> Capabilities — implemented vs roadmap
          </h3>
          <div className="cap-grid">
            <div>
              <p className="nav-label good">Implemented in this prototype</p>
              <ul className="cap-list">
                {IMPLEMENTED.map(([k, v]) => (
                  <li key={k}>
                    <CircleCheck size={15} className="ok" />
                    <div>
                      <b>{k}</b>
                      <p className="faint small">{v}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="nav-label">Roadmap — not implemented yet</p>
              <ul className="cap-list roadmap">
                {ROADMAP.map(([k, v]) => (
                  <li key={k}>
                    <CircleDashed size={15} />
                    <div>
                      <b>{k}</b>
                      <p className="faint small">{v}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <div className="two-col">
          <section className="panel-card">
            <h3>
              <GitBranch size={16} /> LangGraph structure (live from the server)
            </h3>
            {graph ? (
              <div className="graphs">
                {Object.entries(graph).map(([k, g]) => (
                  <GraphFlow key={k} name={k} g={g} />
                ))}
              </div>
            ) : (
              <p className="faint small">Graph unavailable.</p>
            )}
          </section>
          <section className="panel-card">
            <h3>
              <Layers size={16} /> Registered workspaces & plugins
            </h3>
            <ul className="registry">
              {config?.agents.map((a) => (
                <li key={a.id}>
                  <IconTile name={a.icon} color={a.color} size={30} iconSize={15} />
                  <div>
                    <b>{a.name}</b>
                    <p className="faint small">
                      Knowledge: {a.knowledge_collections.join(", ")}
                      {a.tools.length ? ` · Tools: ${a.tools.length}` : ""}
                    </p>
                    {a.uses_plugins && (
                      <div className="chips">
                        {config.plugins
                          .filter((p) => p.agent === a.id)
                          .map((p) => (
                            <span key={p.id} className="chip">
                              <DynamicIcon name={p.icon} size={11} /> {p.name} · {p.tools.length} tools
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            <p className="faint small">
              Add a workspace by dropping a module in <code>backend/nexgraft/agents/</code>, or an engineering domain in{" "}
              <code>backend/nexgraft/plugins/hardware/</code>.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
