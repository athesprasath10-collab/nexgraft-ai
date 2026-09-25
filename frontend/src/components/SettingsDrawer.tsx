import { RotateCcw, X } from "lucide-react";
import { useEffect } from "react";
import { DEFAULT_SETTINGS, useStore } from "../lib/store";
import type { Settings } from "../lib/types";
import { formatBytes } from "../lib/utils";

function Toggle({ label, hint, checked, onChange }: { label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="setting-row">
      <span className="setting-text">
        <span>{label}</span>
        {hint && <span className="faint small">{hint}</span>}
      </span>
      <span className="switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span />
      </span>
    </label>
  );
}

export function SettingsDrawer() {
  const { settingsOpen, setSettingsOpen, settings, updateSettings, status, config } = useStore();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSettingsOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setSettingsOpen]);
  if (!settingsOpen) return null;

  const chatModels = (status?.models || []).filter((m) => !m.is_embedding);
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => updateSettings({ [k]: v } as Partial<Settings>);
  const num = (v: string) => (v.trim() === "" ? null : Number(v));

  return (
    <div className="drawer-scrim" onClick={() => setSettingsOpen(false)}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Settings">
        <header className="drawer-head">
          <h3>Settings</h3>
          <button className="icon-btn" onClick={() => setSettingsOpen(false)} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        <div className="drawer-body">
          <section>
            <h4>Model</h4>
            <label className="field">
              <span>Default chat model</span>
              <select value={settings.model || ""} onChange={(e) => set("model", e.target.value || null)}>
                <option value="">Auto ({status?.default_model || "first Qwen model"})</option>
                {chatModels.map((m) => (
                  <option key={m.name} value={m.name}>
                    {m.name} · {m.parameter_size} · {formatBytes(m.size)}
                  </option>
                ))}
              </select>
            </label>
            <details className="field-group">
              <summary>Per-workspace models (optional)</summary>
              <p className="faint small">
                e.g. a coder model for Bioinformatics. On a 4 GB GPU, switching models costs a few seconds of loading each time.
              </p>
              {config?.agents.map((a) => (
                <label key={a.id} className="field inline">
                  <span>{a.short_name}</span>
                  <select value={settings.agentModels[a.id] || ""} onChange={(e) => set("agentModels", { ...settings.agentModels, [a.id]: e.target.value })}>
                    <option value="">Same as default</option>
                    {chatModels.map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.name}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
            </details>
          </section>

          <section>
            <h4>Orchestration</h4>
            <label className="field">
              <span>Router</span>
              <select value={settings.router} onChange={(e) => set("router", e.target.value as Settings["router"])}>
                <option value="hybrid">LLM analyzer + keyword fallback (recommended)</option>
                <option value="heuristic">Keyword router only (fastest)</option>
              </select>
            </label>
            <Toggle label="Run plans automatically" hint="Skip the plan review step in the Orchestrator" checked={settings.autoRun} onChange={(v) => set("autoRun", v)} />
            <Toggle label="Unified synthesis" hint="Combine multi-workspace results into one summary" checked={settings.synthesis} onChange={(v) => set("synthesis", v)} />
          </section>

          <section>
            <h4>Knowledge & tools</h4>
            <Toggle label="Local knowledge base (RAG)" hint="Retrieve from knowledge/ collections" checked={settings.useKnowledge} onChange={(v) => set("useKnowledge", v)} />
            <Toggle label="Literature search (Europe PMC)" hint="Medical Research AI · needs internet" checked={settings.literature} onChange={(v) => set("literature", v)} />
          </section>

          <section>
            <h4>Generation</h4>
            <div className="field-row">
              <label className="field">
                <span>Context (tokens)</span>
                <input type="number" min={1024} step={1024} placeholder={String(config?.defaults.num_ctx ?? 8192)} value={settings.numCtx ?? ""} onChange={(e) => set("numCtx", num(e.target.value))} />
              </label>
              <label className="field">
                <span>Max output</span>
                <input type="number" min={64} step={64} placeholder={String(config?.defaults.num_predict ?? 1200)} value={settings.numPredict ?? ""} onChange={(e) => set("numPredict", num(e.target.value))} />
              </label>
              <label className="field">
                <span>Temperature</span>
                <input type="number" min={0} max={2} step={0.1} placeholder="auto" value={settings.temperature ?? ""} onChange={(e) => set("temperature", num(e.target.value))} />
              </label>
            </div>
            <p className="faint small">Smaller context = less VRAM. 8192 suits 3B models on a 4 GB GPU; try 4096 for 4B+ models.</p>
          </section>

          <section>
            <h4>Interface</h4>
            <label className="field">
              <span>3D hero</span>
              <select value={settings.hero} onChange={(e) => set("hero", e.target.value as Settings["hero"])}>
                <option value="webgl">Interactive 3D (WebGL, low-power GPU)</option>
                <option value="lite">Lite orbit (CSS, lowest GPU use)</option>
                <option value="off">Off (static)</option>
              </select>
            </label>
            <label className="field">
              <span>Theme</span>
              <select value={settings.theme} onChange={(e) => set("theme", e.target.value as Settings["theme"])}>
                <option value="dark">Dark</option>
                <option value="light">Light</option>
              </select>
            </label>
          </section>
        </div>

        <footer className="drawer-foot">
          <button className="btn btn-ghost btn-sm" onClick={() => updateSettings(DEFAULT_SETTINGS)}>
            <RotateCcw size={14} /> Reset to defaults
          </button>
          <span className="faint small">Saved in this browser</span>
        </footer>
      </aside>
    </div>
  );
}
