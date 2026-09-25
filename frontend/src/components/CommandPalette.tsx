import { ArrowRight, CornerDownLeft, Database, MessageSquare, Moon, Plus, Search, Server, Settings, Sparkles, Sun, Workflow } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { navigate, type Route } from "../lib/route";
import { useStore } from "../lib/store";
import { cx, seedComposer, timeAgo } from "../lib/utils";
import { DynamicIcon } from "./Icon";

interface Command {
  id: string;
  group: string;
  label: string;
  hint?: string;
  icon: ReactNode;
  keywords?: string;
  run: () => void;
}

/** Substring match on the label (best), then keywords/hint, then word-initials (e.g. "hd" → Hardware Design). */
function score(query: string, c: { label: string; keywords?: string; hint?: string }): number {
  const q = query.trim().toLowerCase();
  if (!q) return 0;
  const label = c.label.toLowerCase();
  const li = label.indexOf(q);
  if (li >= 0) return 200 - li + (li === 0 || label[li - 1] === " " ? 20 : 0);
  if (`${c.keywords || ""} ${c.hint || ""}`.toLowerCase().includes(q)) return 80;
  const initials = label.split(/[^a-z0-9]+/).filter(Boolean).map((w) => w[0]).join("");
  return initials.includes(q) ? 40 : -1;
}

export function CommandPalette({ route }: { route: Route }) {
  const { paletteOpen, setPaletteOpen, config, conversations, settings, updateSettings, newConversation, setActive, setSettingsOpen } = useStore();
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const mode = route.name === "workspace" ? route.agent : "orchestrator";

  useEffect(() => {
    if (paletteOpen) {
      setQuery("");
      setIndex(0);
      requestAnimationFrame(() => input.current?.focus());
    }
  }, [paletteOpen]);

  const commands = useMemo<Command[]>(() => {
    const close = () => setPaletteOpen(false);
    const go = (r: Route) => () => {
      navigate(r);
      close();
    };
    const cmds: Command[] = [
      {
        id: "new-task",
        group: "Actions",
        label: "New orchestrated task",
        hint: "Auto-route across workspaces",
        icon: <Plus size={16} />,
        keywords: "create start",
        run: () => {
          newConversation("orchestrator");
          navigate({ name: "home" });
          close();
        },
      },
    ];
    if (mode !== "orchestrator") {
      const a = config?.agents.find((x) => x.id === mode);
      cmds.push({
        id: "new-chat",
        group: "Actions",
        label: `New chat in ${a?.short_name || mode}`,
        icon: <MessageSquare size={16} />,
        run: () => {
          newConversation(mode);
          close();
        },
      });
    }
    cmds.push(
      {
        id: "theme",
        group: "Actions",
        label: settings.theme === "dark" ? "Switch to light theme" : "Switch to dark theme",
        icon: settings.theme === "dark" ? <Sun size={16} /> : <Moon size={16} />,
        keywords: "appearance mode color",
        run: () => {
          updateSettings({ theme: settings.theme === "dark" ? "light" : "dark" });
          close();
        },
      },
      {
        id: "settings",
        group: "Actions",
        label: "Open settings",
        hint: "Model, router, language, 3D hero",
        icon: <Settings size={16} />,
        keywords: "preferences model",
        run: () => {
          close();
          setSettingsOpen(true);
        },
      },
      { id: "go-home", group: "Go to", label: "Orchestrator", hint: "auto-route", icon: <Workflow size={16} />, run: go({ name: "home" }) },
    );
    for (const a of config?.agents || []) {
      cmds.push({
        id: `go-${a.id}`,
        group: "Go to",
        label: a.name,
        hint: a.tagline,
        icon: <DynamicIcon name={a.icon} size={16} style={{ color: a.color }} />,
        keywords: a.capabilities.join(" "),
        run: go({ name: "workspace", agent: a.id }),
      });
    }
    cmds.push(
      { id: "go-knowledge", group: "Go to", label: "Knowledge base", icon: <Database size={16} />, keywords: "rag documents", run: go({ name: "knowledge" }) },
      { id: "go-system", group: "Go to", label: "System & capabilities", icon: <Server size={16} />, keywords: "gpu ollama models status", run: go({ name: "system" }) },
    );
    for (const a of config?.agents || []) {
      for (const ex of a.examples.slice(0, 2)) {
        cmds.push({
          id: `ex-${a.id}-${ex.slice(0, 20)}`,
          group: "Try a request",
          label: ex,
          icon: <Sparkles size={16} style={{ color: a.color }} />,
          run: () => {
            newConversation("orchestrator");
            navigate({ name: "home" });
            close();
            setTimeout(() => seedComposer(ex), 80);
          },
        });
      }
    }
    const recent = Object.values(conversations)
      .filter((c) => c.turns.length)
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 8);
    for (const c of recent) {
      const agent = config?.agents.find((a) => a.id === c.mode);
      cmds.push({
        id: `conv-${c.id}`,
        group: "Recent",
        label: c.title,
        hint: `${agent?.short_name || "Orchestrator"} · ${timeAgo(c.updatedAt)}`,
        icon: <MessageSquare size={16} style={{ color: agent?.color }} />,
        run: () => {
          setActive(c.mode, c.id);
          navigate(c.mode === "orchestrator" ? { name: "home" } : { name: "workspace", agent: c.mode });
          close();
        },
      });
    }
    return cmds;
  }, [config, conversations, settings.theme, mode, newConversation, setActive, setPaletteOpen, setSettingsOpen, updateSettings]);

  const results = useMemo(() => {
    if (!query.trim()) return commands.filter((c) => c.group !== "Try a request" || commands.indexOf(c) < 40);
    const scored = commands.map((c) => ({ c, s: score(query, c) })).filter((x) => x.s >= 0);
    // keep groups together, ordered by their best match
    const best = new Map<string, number>();
    for (const x of scored) best.set(x.c.group, Math.max(best.get(x.c.group) ?? -1, x.s));
    return scored
      .sort((a, b) => (best.get(b.c.group)! - best.get(a.c.group)!) || a.c.group.localeCompare(b.c.group) || b.s - a.s)
      .map((x) => x.c)
      .slice(0, 30);
  }, [commands, query]);

  useEffect(() => setIndex(0), [query]);
  useEffect(() => {
    list.current?.querySelector(`[data-idx="${index}"]`)?.scrollIntoView({ block: "nearest" });
  }, [index]);

  if (!paletteOpen) return null;

  let lastGroup = "";
  return (
    <div className="palette-scrim" onClick={() => setPaletteOpen(false)}>
      <div className="palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <div className="palette-input">
          <Search size={17} />
          <input
            ref={input}
            value={query}
            placeholder="Search workspaces, actions, examples, conversations…"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setIndex((i) => Math.min(i + 1, results.length - 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setIndex((i) => Math.max(i - 1, 0));
              } else if (e.key === "Enter") {
                e.preventDefault();
                results[index]?.run();
              } else if (e.key === "Escape") setPaletteOpen(false);
            }}
          />
          <span className="kbd">Esc</span>
        </div>
        <div className="palette-list" ref={list}>
          {results.length === 0 && <p className="palette-empty">No matches.</p>}
          {results.map((c, i) => {
            const header = c.group !== lastGroup ? c.group : null;
            lastGroup = c.group;
            return (
              <div key={c.id}>
                {header && <p className="palette-group">{header}</p>}
                <button data-idx={i} className={cx("palette-item", i === index && "active")} onMouseMove={() => setIndex(i)} onClick={c.run}>
                  <span className="palette-icon">{c.icon}</span>
                  <span className="palette-label">{c.label}</span>
                  {c.hint && <span className="palette-hint">{c.hint}</span>}
                  {i === index ? <CornerDownLeft size={14} className="palette-enter" /> : <ArrowRight size={14} className="palette-enter dim" />}
                </button>
              </div>
            );
          })}
        </div>
        <div className="palette-foot">
          <span>
            <span className="kbd">↑</span> <span className="kbd">↓</span> navigate
          </span>
          <span>
            <span className="kbd">Enter</span> open
          </span>
          <span className="faint">NEXGRAFT command palette</span>
        </div>
      </div>
    </div>
  );
}
