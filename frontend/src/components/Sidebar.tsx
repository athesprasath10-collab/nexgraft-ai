import { Database, Moon, PanelLeftClose, Plus, Server, Settings, Sun, Trash2, Workflow } from "lucide-react";
import { useMemo } from "react";
import { hrefFor, navigate, type Route } from "../lib/route";
import { useStore } from "../lib/store";
import { cx, timeAgo } from "../lib/utils";
import { DynamicIcon } from "./Icon";

export function Logo({ small = false }: { small?: boolean }) {
  return (
    <span className={cx("logo", small && "small")}>
      <svg viewBox="0 0 64 64" className="logo-mark" aria-hidden>
        <defs>
          <linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#a594ff" />
            <stop offset=".4" stopColor="#6ab8ff" />
            <stop offset=".72" stopColor="#3fe0b0" />
            <stop offset="1" stopColor="#ffc266" />
          </linearGradient>
        </defs>
        <rect x="2" y="2" width="60" height="60" rx="17" className="logo-bg" />
        <path d="M19 45V19l26 26V19" fill="none" stroke="url(#lg)" strokeWidth="6.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="logo-text">
        NEXGRAFT<span className="logo-ai">AI</span>
      </span>
    </span>
  );
}

export function StatusPill() {
  const status = useStore((s) => s.status);
  const model = useStore((s) => s.settings.model) || status?.default_model;
  const ok = status?.ollama.reachable;
  const running = status?.running.find((r) => r.name === model);
  return (
    <a className={cx("status-pill", ok ? "ok" : status ? "down" : "unknown")} href={hrefFor({ name: "system" })} title="Local AI runtime status">
      <span className="dot" />
      <span className="status-text">
        <span>{ok ? "Ollama connected" : status ? "Ollama offline" : "Checking…"}</span>
        <span className="faint mono">
          {ok ? model || "no model" : status ? "start the Ollama app" : ""}
          {running ? ` · GPU ${running.gpu_percent}%` : ""}
        </span>
      </span>
    </a>
  );
}

export function Sidebar({ route }: { route: Route }) {
  const config = useStore((s) => s.config);
  const conversations = useStore((s) => s.conversations);
  const activeByMode = useStore((s) => s.activeByMode);
  const { newConversation, setActive, deleteConversation, setSettingsOpen, sidebarOpen, setSidebarOpen, settings, updateSettings } = useStore();

  const mode = route.name === "workspace" ? route.agent : "orchestrator";
  const recent = useMemo(
    () =>
      Object.values(conversations)
        .filter((c) => c.turns.length > 0)
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .slice(0, 30),
    [conversations],
  );

  const go = (r: Route) => {
    navigate(r);
    setSidebarOpen(false);
  };

  return (
    <>
      <div className={cx("sidebar-scrim", sidebarOpen && "show")} onClick={() => setSidebarOpen(false)} />
      <aside className={cx("sidebar", sidebarOpen && "open")}>
        <div className="sidebar-top">
          <a href="#/" onClick={() => setSidebarOpen(false)}>
            <Logo />
          </a>
          <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close menu">
            <PanelLeftClose size={18} />
          </button>
        </div>

        <button
          className="new-btn"
          onClick={() => {
            newConversation(mode);
            setSidebarOpen(false);
            if (route.name !== "home" && route.name !== "workspace") navigate({ name: "home" });
          }}
        >
          <Plus size={16} /> New {mode === "orchestrator" ? "task" : "chat"}
          <span className="kbd">⌘K</span>
        </button>

        <nav className="nav">
          <a className={cx("nav-item", route.name === "home" && "active")} href="#/" onClick={() => setSidebarOpen(false)}>
            <span className="nav-icon orch">
              <Workflow size={16} />
            </span>
            <span>Orchestrator</span>
            <span className="nav-hint">auto-route</span>
          </a>
          <p className="nav-label">Workspaces</p>
          {config?.agents.map((a) => (
            <a
              key={a.id}
              className={cx("nav-item", route.name === "workspace" && route.agent === a.id && "active")}
              href={hrefFor({ name: "workspace", agent: a.id })}
              onClick={() => setSidebarOpen(false)}
              style={{ "--c": a.color } as React.CSSProperties}
            >
              <span className="nav-icon">
                <DynamicIcon name={a.icon} size={16} />
              </span>
              <span>{a.name}</span>
            </a>
          ))}
          <p className="nav-label">Resources</p>
          <a className={cx("nav-item", route.name === "knowledge" && "active")} href="#/knowledge" onClick={() => setSidebarOpen(false)}>
            <span className="nav-icon plain">
              <Database size={16} />
            </span>
            <span>Knowledge base</span>
          </a>
          <a className={cx("nav-item", route.name === "system" && "active")} href="#/system" onClick={() => setSidebarOpen(false)}>
            <span className="nav-icon plain">
              <Server size={16} />
            </span>
            <span>System & capabilities</span>
          </a>
        </nav>

        <div className="recent">
          <p className="nav-label">Recent</p>
          {recent.length === 0 && <p className="faint small pad-x">Your conversations stay on this computer.</p>}
          {recent.map((c) => {
            const agent = config?.agents.find((a) => a.id === c.mode);
            const active = activeByMode[c.mode] === c.id && (c.mode === mode);
            return (
              <div key={c.id} className={cx("recent-item", active && "active")}>
                <button
                  className="recent-main"
                  onClick={() => {
                    setActive(c.mode, c.id);
                    go(c.mode === "orchestrator" ? { name: "home" } : { name: "workspace", agent: c.mode });
                  }}
                  title={c.title}
                >
                  <span className="recent-dot" style={{ background: agent?.color || "var(--grad-brand)" }} />
                  <span className="recent-title">{c.title}</span>
                  <span className="recent-time">{timeAgo(c.updatedAt)}</span>
                </button>
                <button className="icon-btn sm recent-del" onClick={() => deleteConversation(c.id)} title="Delete conversation" aria-label="Delete conversation">
                  <Trash2 size={13} />
                </button>
              </div>
            );
          })}
        </div>

        <div className="sidebar-bottom">
          <StatusPill />
          <div className="sidebar-tools">
            <button className="icon-btn" onClick={() => updateSettings({ theme: settings.theme === "dark" ? "light" : "dark" })} title="Toggle theme">
              {settings.theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
            </button>
            <button className="icon-btn" onClick={() => setSettingsOpen(true)} title="Settings">
              <Settings size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
