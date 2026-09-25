import { ArrowRight, Blocks, Cpu, Menu, Network, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { Composer } from "../components/Composer";
import { ConversationView } from "../components/Conversation";
import { HeroScene } from "../components/HeroScene";
import { DynamicIcon, IconTile } from "../components/Icon";
import { isActive, sendOrchestrated, stopTurn } from "../lib/engine";
import { hrefFor } from "../lib/route";
import { useStore } from "../lib/store";
import type { AssistantTurn } from "../lib/types";

const MULTI_EXAMPLE =
  "I want to develop a wearable device for monitoring physiological parameters, and I also want to understand the relevant biological data.";

const PRINCIPLES = [
  { label: "Understand the problem", icon: Sparkles },
  { label: "Find the right expertise", icon: Network },
  { label: "Connect the right resources", icon: Blocks },
  { label: "Generate useful output", icon: Cpu },
];

export function useActiveTurn(convId?: string) {
  return useStore((s) => {
    const conv = convId ? s.conversations[convId] : undefined;
    const last = conv?.turns[conv.turns.length - 1];
    return last?.role === "assistant" && (last.phase === "analyzing" || last.phase === "running") ? (last as AssistantTurn) : undefined;
  });
}

export function HomeView() {
  const config = useStore((s) => s.config);
  const convId = useStore((s) => s.activeByMode.orchestrator);
  const conv = useStore((s) => (convId ? s.conversations[convId] : undefined));
  const { ensureConversation, newConversation, setSidebarOpen } = useStore();
  const active = useActiveTurn(convId);
  const [seed, setSeed] = useState<{ text: string; n: number }>();

  const send = (text: string, attachments: Parameters<typeof sendOrchestrated>[2], voice: boolean) => {
    const id = ensureConversation("orchestrator");
    sendOrchestrated(id, text, attachments, voice);
  };
  const stop = () => active && isActive(active.id) && stopTurn(active.id);
  const pickExample = (text: string) => setSeed({ text, n: Date.now() });

  if (!conv || conv.turns.length === 0) {
    return (
      <div className="view scroll-area">
        <button className="icon-btn mobile-menu mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
          <Menu size={20} />
        </button>
        <div className="home">
          <section className="hero">
            <div className="hero-visual">
              <HeroScene />
            </div>
            <div className="hero-copy">
              <span className="eyebrow">
                <span className="eyebrow-dot" /> One Platform · Multiple Experts · One Intelligent Solution
              </span>
              <h1>
                What are you <span className="gradient-text">working on?</span>
              </h1>
              <p className="lede">
                Describe your problem, idea or task. NEXGRAFT understands it, routes each part to the right specialised workspace, connects
                knowledge and tools, and brings the results together — running locally on your machine.
              </p>
            </div>
            <Composer variant="hero" placeholder="Describe your problem, idea or task…" busy={!!active} onSend={send} onStop={stop} seed={seed} autoFocus />
            <ol className="principles">
              {PRINCIPLES.map((p, i) => (
                <li key={p.label}>
                  <p.icon size={14} />
                  <span>{p.label}</span>
                  {i < PRINCIPLES.length - 1 && <ArrowRight size={13} className="faint" />}
                </li>
              ))}
            </ol>
          </section>

          <section className="examples">
            <div className="section-head">
              <h2>Try a request</h2>
              <span className="faint small">The orchestrator activates only the workspaces a request needs.</span>
            </div>
            <div className="example-grid">
              {config?.agents.map((a) => (
                <button key={a.id} className="example-card spot" style={{ "--c": a.color } as React.CSSProperties} onClick={() => pickExample(a.examples[0])}>
                  <span className="example-kicker">
                    <DynamicIcon name={a.icon} size={13} /> {a.short_name}
                  </span>
                  <span className="example-text">{a.examples[0]}</span>
                </button>
              ))}
              <button className="example-card multi spot" onClick={() => pickExample(MULTI_EXAMPLE)}>
                <span className="example-kicker">
                  <Network size={13} /> Multi-agent · task graph
                </span>
                <span className="example-text">{MULTI_EXAMPLE}</span>
              </button>
            </div>
          </section>

          <section className="workspaces">
            <div className="section-head">
              <h2>Specialised workspaces</h2>
              <span className="faint small">Or go straight to one expert.</span>
            </div>
            <div className="ws-grid">
              {config?.agents.map((a) => (
                <a key={a.id} className="ws-card spot" href={hrefFor({ name: "workspace", agent: a.id })} style={{ "--c": a.color } as React.CSSProperties}>
                  <div className="ws-card-top">
                    <IconTile name={a.icon} color={a.color} size={40} iconSize={20} />
                    <ArrowRight size={16} className="ws-card-arrow" />
                  </div>
                  <h3>{a.name}</h3>
                  <p className="muted small">{a.tagline}</p>
                  <div className="chips">
                    {a.capabilities.slice(0, 3).map((c) => (
                      <span key={c} className="chip">
                        {c}
                      </span>
                    ))}
                  </div>
                  {a.boundary && (
                    <p className="ws-boundary">
                      <ShieldCheck size={12} /> {a.boundary}
                    </p>
                  )}
                </a>
              ))}
            </div>
          </section>
          <footer className="home-foot faint small">
            NEXGRAFT AI prototype v{config?.app_version} · Local LLM via Ollama · LangGraph orchestration · Your data stays on this computer (literature
            search and browser voice input use the internet).
          </footer>
        </div>
      </div>
    );
  }

  return (
    <div className="view chat-layout">
      <header className="chat-header">
        <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
          <Menu size={20} />
        </button>
        <span className="chat-kicker">
          <DynamicIcon name="orchestrator" size={15} /> Orchestrator
        </span>
        <h2 className="chat-title">{conv.title}</h2>
        <button className="btn btn-ghost btn-sm" onClick={() => newConversation("orchestrator")}>
          <Plus size={14} /> New task
        </button>
      </header>
      <div className="scroll-area">
        <ConversationView conv={conv} />
      </div>
      <div className="dock">
        <Composer variant="dock" placeholder="Ask a follow-up or describe a new problem…" busy={!!active} onSend={send} onStop={stop} seed={seed} />
        <p className="dock-hint faint">NEXGRAFT provides information and guidance. You stay in control of execution, experiments and decisions.</p>
      </div>
    </div>
  );
}
