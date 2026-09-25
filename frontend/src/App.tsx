import { LoaderCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { useEffect } from "react";
import { CommandPalette } from "./components/CommandPalette";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { Logo, Sidebar } from "./components/Sidebar";
import { Toasts } from "./components/Toast";
import { api, ApiError } from "./lib/api";
import { useRoute } from "./lib/route";
import { useStore } from "./lib/store";
import { HomeView } from "./views/HomeView";
import { KnowledgeView } from "./views/KnowledgeView";
import { SystemView } from "./views/SystemView";
import { WorkspaceView } from "./views/WorkspaceView";

function Backdrop() {
  return (
    <div className="backdrop" aria-hidden>
      <div className="aurora a1" />
      <div className="aurora a2" />
      <div className="aurora a3" />
      <div className="aurora a4" />
    </div>
  );
}

function loadConfig() {
  const { setConfig } = useStore.getState();
  api
    .config()
    .then((c) => setConfig(c))
    .catch((e) => setConfig(null, e instanceof ApiError ? e.message : String(e)));
}

function ServerDown({ error }: { error: string }) {
  return (
    <div className="server-down">
      <Logo />
      <div className="panel-card">
        <h2>
          <TriangleAlert size={18} /> Can't reach the NEXGRAFT server
        </h2>
        <p className="muted">{error}</p>
        <ol>
          <li>
            Start the backend: <code>python run.py</code> (or <code>start.bat</code> on Windows)
          </li>
          <li>
            Make sure Ollama is running (Ollama app in the tray, or <code>ollama serve</code>)
          </li>
        </ol>
        <button className="btn btn-primary" onClick={loadConfig}>
          <RefreshCw size={15} /> Retry
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const route = useRoute();
  const config = useStore((s) => s.config);
  const configError = useStore((s) => s.configError);
  const theme = useStore((s) => s.settings.theme);

  useEffect(loadConfig, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const poll = () =>
      api
        .status()
        .then((s) => useStore.getState().setStatus(s))
        .catch(() => useStore.getState().setStatus(null));
    poll();
    const t = setInterval(poll, 20000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        const st = useStore.getState();
        st.setPaletteOpen(!st.paletteOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Cursor spotlight on cards (.spot) — one delegated listener, CSS does the rest.
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const el = (e.target as Element | null)?.closest?.(".spot") as HTMLElement | null;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => document.removeEventListener("pointermove", onMove);
  }, []);

  if (!config) {
    return (
      <>
        <Backdrop />
        {configError ? (
          <ServerDown error={configError} />
        ) : (
          <div className="boot">
            <Logo />
            <LoaderCircle className="spin" size={20} />
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <Backdrop />
      <div className="app">
        <Sidebar route={route} />
        <main className="main">
          {route.name === "home" && <HomeView />}
          {route.name === "workspace" && <WorkspaceView key={route.agent} agentId={route.agent} />}
          {route.name === "knowledge" && <KnowledgeView />}
          {route.name === "system" && <SystemView />}
        </main>
      </div>
      <SettingsDrawer />
      <CommandPalette route={route} />
      <Toasts />
    </>
  );
}
