import { BookOpen, Calculator, Code2, FlaskConical, Library, Menu, PanelRight, Plus, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Composer } from "../components/Composer";
import { ConversationView } from "../components/Conversation";
import { DynamicIcon, IconTile } from "../components/Icon";
import { CodeBlock } from "../components/Markdown";
import { SourceItem } from "../components/SourceList";
import { ToolForm, ToolPanel } from "../components/ToolPanel";
import { isActive, sendDirect, stopTurn } from "../lib/engine";
import { agentById, useStore } from "../lib/store";
import type { AgentSpec, Conversation, Source } from "../lib/types";
import { cx, extractCodeBlocks } from "../lib/utils";
import { useActiveTurn } from "./HomeView";

type Tab = { id: string; label: string; icon: typeof Code2 };

const PANEL_TABS: Record<string, Tab[]> = {
  code: [
    { id: "code", label: "Code & workflow", icon: Code2 },
    { id: "tools", label: "Sequence toolkit", icon: FlaskConical },
  ],
  research: [
    { id: "sources", label: "Sources", icon: Library },
    { id: "tools", label: "Literature search", icon: BookOpen },
  ],
  engineering: [{ id: "tools", label: "Calculators", icon: Calculator }],
};

function CodePanel({ conv, runnable }: { conv?: Conversation; runnable: boolean }) {
  const blocks = useMemo(() => {
    const out: { key: string; lang: string; code: string; label: string; attachments: string[] }[] = [];
    let attachments: string[] = [];
    let n = 0;
    for (const t of conv?.turns || []) {
      if (t.role === "user") {
        attachments = t.attachments.map((a) => a.id);
        continue;
      }
      n += 1;
      for (const task of t.tasks) {
        if (task.status === "generating") continue;
        extractCodeBlocks(task.content).forEach((b, i) => out.push({ key: `${t.id}-${task.id}-${i}`, ...b, label: `Answer ${n}`, attachments }));
      }
    }
    return out.reverse();
  }, [conv]);

  if (!blocks.length)
    return (
      <div className="panel-empty">
        <Code2 size={22} />
        <p>Code and workflow scripts from answers collect here.</p>
        <p className="faint small">Review a script, then run it locally with one click — attached files are available to it by name.</p>
      </div>
    );
  return (
    <div className="code-panel">
      {blocks.map((b) => (
        <div key={b.key} className="code-panel-item">
          <span className="faint small">{b.label}</span>
          <CodeBlock lang={b.lang} code={b.code} runnable={runnable} attachmentIds={b.attachments} />
        </div>
      ))}
    </div>
  );
}

function SourcesPanel({ conv }: { conv?: Conversation }) {
  const sources = useMemo(() => {
    const seen = new Set<string>();
    const out: Source[] = [];
    for (const t of [...(conv?.turns || [])].reverse()) {
      if (t.role !== "assistant") continue;
      for (const task of t.tasks)
        for (const s of task.sources) {
          const key = s.url || `${s.doc}#${s.heading}`;
          if (!seen.has(key)) {
            seen.add(key);
            out.push(s);
          }
        }
    }
    return out;
  }, [conv]);
  if (!sources.length)
    return (
      <div className="panel-empty">
        <Library size={22} />
        <p>Literature and knowledge-base sources used in answers appear here.</p>
        <p className="faint small">Answers cite them as numbered references.</p>
      </div>
    );
  const lit = sources.filter((s) => s.kind === "literature");
  const kb = sources.filter((s) => s.kind !== "literature");
  return (
    <div className="sources-panel">
      {lit.length > 0 && <p className="nav-label">Literature · Europe PMC</p>}
      <ol className="source-list">{lit.map((s, i) => <SourceItem key={i} s={{ ...s, n: i + 1 }} />)}</ol>
      {kb.length > 0 && <p className="nav-label">NEXGRAFT knowledge base</p>}
      <ol className="source-list">{kb.map((s, i) => <SourceItem key={i} s={{ ...s, n: lit.length + i + 1 }} />)}</ol>
    </div>
  );
}

function EmptyWorkspace({ spec, examples, onPick }: { spec: AgentSpec; examples: string[]; onPick: (t: string) => void }) {
  return (
    <div className="ws-empty fade-up">
      <IconTile name={spec.icon} color={spec.color} size={56} iconSize={26} />
      <h2>{spec.name}</h2>
      <p className="muted">{spec.description}</p>
      <div className="ws-examples">
        {examples.map((e) => (
          <button key={e} className="example-card" style={{ "--c": spec.color } as React.CSSProperties} onClick={() => onPick(e)}>
            <span className="example-text">{e}</span>
          </button>
        ))}
      </div>
      <div className="user-controls">
        <p className="nav-label">
          <ShieldCheck size={12} /> You stay in control of
        </p>
        <ul>
          {spec.user_controls.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export function WorkspaceView({ agentId }: { agentId: string }) {
  const config = useStore((s) => s.config);
  const spec = agentById(config, agentId);
  const convId = useStore((s) => s.activeByMode[agentId]);
  const conv = useStore((s) => (convId ? s.conversations[convId] : undefined));
  const { ensureConversation, newConversation, setPlugin, setSidebarOpen } = useStore();
  const active = useActiveTurn(convId);
  const tabs = spec ? PANEL_TABS[spec.workspace] || [] : [];
  const [tab, setTab] = useState(tabs[0]?.id);
  const [panelOpen, setPanelOpen] = useState(() => window.innerWidth > 1100);
  const [seed, setSeed] = useState<{ text: string; n: number }>();
  const [pluginDraft, setPluginDraft] = useState<string | null>(null);

  useEffect(() => setTab(tabs[0]?.id), [agentId]); // eslint-disable-line react-hooks/exhaustive-deps

  const plugins = (config?.plugins || []).filter((p) => p.agent === agentId);
  const plugin = conv ? conv.plugin ?? null : pluginDraft;
  const choosePlugin = (id: string | null) => (conv ? setPlugin(conv.id, id) : setPluginDraft(id));
  const tools = (config?.tools || []).filter((t) => {
    if (!spec) return false;
    if (spec.tools.includes(t.id)) return true;
    return t.agent === agentId && t.plugin && (!plugin || t.plugin === plugin);
  });

  if (!spec) return <div className="view center faint">Unknown workspace.</div>;

  const send = (text: string, attachments: Parameters<typeof sendDirect>[4], voice: boolean) => {
    const id = convId && conv ? convId : ensureConversation(agentId);
    if (!conv && plugin) setPlugin(id, plugin);
    sendDirect(id, agentId, plugin, text, attachments, voice);
  };
  const stop = () => active && isActive(active.id) && stopTurn(active.id);
  const pick = (text: string) => setSeed({ text, n: Date.now() });
  const activePlugin = plugins.find((p) => p.id === plugin);
  const examples = activePlugin?.examples.length ? [...activePlugin.examples, ...spec.examples.slice(0, 2)] : spec.examples;
  const runnable = !!config?.features.code_runner;

  return (
    <div className="view workspace" style={{ "--c": spec.color } as React.CSSProperties}>
      <header className="ws-header">
        <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
          <Menu size={20} />
        </button>
        <IconTile name={spec.icon} color={spec.color} size={38} iconSize={19} />
        <div className="ws-heading">
          <h2>{spec.name}</h2>
          <p className="faint small">{spec.tagline}</p>
        </div>
        <div className="ws-header-actions">
          <button className="btn btn-ghost btn-sm" onClick={() => newConversation(agentId, plugin)}>
            <Plus size={14} /> New chat
          </button>
          {tabs.length > 0 && (
            <button className={cx("icon-btn", panelOpen && "active")} onClick={() => setPanelOpen(!panelOpen)} title="Toggle side panel">
              <PanelRight size={17} />
            </button>
          )}
        </div>
      </header>

      {plugins.length > 0 && (
        <div className="plugin-bar" role="radiogroup" aria-label="Engineering domain plugin">
          <span className="nav-label">Domain plugin</span>
          <button className={cx("plugin-pill", !plugin && "active")} onClick={() => choosePlugin(null)}>
            <DynamicIcon name="cpu" size={13} /> General engineering
          </button>
          {plugins.map((p) => (
            <button key={p.id} className={cx("plugin-pill", plugin === p.id && "active")} onClick={() => choosePlugin(p.id)} title={p.description}>
              <DynamicIcon name={p.icon} size={13} /> {p.name}
            </button>
          ))}
        </div>
      )}

      <div className={cx("ws-body", panelOpen && tabs.length > 0 && "with-panel")}>
        <div className="ws-chat">
          <div className="scroll-area">
            {conv && conv.turns.length > 0 ? <ConversationView conv={conv} /> : <EmptyWorkspace spec={spec} examples={examples} onPick={pick} />}
          </div>
          <div className="dock">
            <Composer
              variant="dock"
              accent={spec.color}
              placeholder={
                spec.workspace === "code"
                  ? "Describe a biological or computational task… (paste sequences or attach FASTA)"
                  : spec.workspace === "research"
                    ? "Ask a medical or healthcare research question…"
                    : spec.workspace === "engineering"
                      ? `Describe your engineering requirement${activePlugin ? ` (${activePlugin.name})` : ""}…`
                      : "Ask anything…"
              }
              busy={!!active}
              onSend={send}
              onStop={stop}
              seed={seed}
            />
            <p className="dock-hint faint">
              <ShieldCheck size={11} /> {spec.boundary || "NEXGRAFT provides information and guidance; you stay in control of decisions."}
            </p>
          </div>
        </div>

        {panelOpen && tabs.length > 0 && (
          <aside className="ws-panel">
            <div className="panel-tabs">
              {tabs.map((t) => (
                <button key={t.id} className={cx("panel-tab", tab === t.id && "active")} onClick={() => setTab(t.id)}>
                  <t.icon size={14} /> {t.label}
                </button>
              ))}
              <button className="icon-btn sm panel-close" onClick={() => setPanelOpen(false)} aria-label="Close panel">
                <X size={14} />
              </button>
            </div>
            <div className="panel-body">
              {tab === "code" && <CodePanel conv={conv} runnable={runnable} />}
              {tab === "sources" && <SourcesPanel conv={conv} />}
              {tab === "tools" && spec.workspace === "research" && tools.map((t) => <ToolForm key={t.id} tool={t} defaultOpen />)}
              {tab === "tools" && spec.workspace !== "research" && (
                <>
                  {spec.workspace === "engineering" && (
                    <p className="panel-intro faint small">
                      {activePlugin ? `${activePlugin.name} calculators.` : "All engineering calculators."} Deterministic formulas — use a result in your prompt so the AI
                      works from verified numbers.
                    </p>
                  )}
                  <ToolPanel key={plugin || "all"} tools={tools} onInsert={(text) => pick(text + "\n\n")} />
                </>
              )}
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
