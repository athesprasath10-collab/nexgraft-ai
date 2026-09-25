import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { AppConfig, AssistantTurn, Conversation, Settings, SystemStatus, Turn } from "./types";

export const DEFAULT_SETTINGS: Settings = {
  model: null,
  agentModels: {},
  router: "hybrid",
  autoRun: false,
  synthesis: true,
  literature: true,
  useKnowledge: true,
  language: "auto",
  numCtx: null,
  numPredict: null,
  temperature: null,
  hero: "webgl",
  theme: "dark",
};

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);

interface State {
  config: AppConfig | null;
  configError: string | null;
  status: SystemStatus | null;
  settings: Settings;
  conversations: Record<string, Conversation>;
  activeByMode: Record<string, string | undefined>;
  settingsOpen: boolean;
  sidebarOpen: boolean;
  paletteOpen: boolean;

  setConfig: (c: AppConfig | null, error?: string | null) => void;
  setStatus: (s: SystemStatus | null) => void;
  updateSettings: (p: Partial<Settings>) => void;
  setSettingsOpen: (open: boolean) => void;
  setSidebarOpen: (open: boolean) => void;
  setPaletteOpen: (open: boolean) => void;
  newConversation: (mode: string, plugin?: string | null) => string;
  ensureConversation: (mode: string) => string;
  setActive: (mode: string, id: string | undefined) => void;
  deleteConversation: (id: string) => void;
  setPlugin: (id: string, plugin: string | null) => void;
  addTurn: (convId: string, turn: Turn) => void;
  updateTurn: (convId: string, turnId: string, fn: (t: AssistantTurn) => AssistantTurn) => void;
}

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      config: null,
      configError: null,
      status: null,
      settings: DEFAULT_SETTINGS,
      conversations: {},
      activeByMode: {},
      settingsOpen: false,
      sidebarOpen: false,
      paletteOpen: false,

      setConfig: (config, error = null) => set({ config, configError: error }),
      setStatus: (status) => set({ status }),
      updateSettings: (p) => set((s) => ({ settings: { ...s.settings, ...p } })),
      setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
      setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
      setPaletteOpen: (paletteOpen) => set({ paletteOpen }),

      newConversation: (mode, plugin = null) => {
        const id = uid();
        const now = Date.now();
        set((s) => ({
          conversations: { ...s.conversations, [id]: { id, title: "New conversation", mode, plugin, createdAt: now, updatedAt: now, turns: [] } },
          activeByMode: { ...s.activeByMode, [mode]: id },
        }));
        return id;
      },

      ensureConversation: (mode) => {
        const { activeByMode, conversations } = get();
        const id = activeByMode[mode];
        if (id && conversations[id]) return id;
        return get().newConversation(mode);
      },

      setActive: (mode, id) => set((s) => ({ activeByMode: { ...s.activeByMode, [mode]: id } })),

      deleteConversation: (id) =>
        set((s) => {
          const conversations = { ...s.conversations };
          delete conversations[id];
          const activeByMode = Object.fromEntries(Object.entries(s.activeByMode).map(([k, v]) => [k, v === id ? undefined : v]));
          return { conversations, activeByMode };
        }),

      setPlugin: (id, plugin) =>
        set((s) => (s.conversations[id] ? { conversations: { ...s.conversations, [id]: { ...s.conversations[id], plugin } } } : {})),

      addTurn: (convId, turn) =>
        set((s) => {
          const conv = s.conversations[convId];
          if (!conv) return {};
          const title =
            conv.turns.length === 0 && turn.role === "user"
              ? turn.content.replace(/\s+/g, " ").slice(0, 64) || turn.attachments[0]?.name || "New conversation"
              : conv.title;
          return { conversations: { ...s.conversations, [convId]: { ...conv, title, turns: [...conv.turns, turn], updatedAt: Date.now() } } };
        }),

      updateTurn: (convId, turnId, fn) =>
        set((s) => {
          const conv = s.conversations[convId];
          if (!conv) return {};
          const turns = conv.turns.map((t) => (t.id === turnId && t.role === "assistant" ? fn(t) : t));
          return { conversations: { ...s.conversations, [convId]: { ...conv, turns, updatedAt: Date.now() } } };
        }),
    }),
    {
      name: "nexgraft-workspace",
      version: 1,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ settings: s.settings, conversations: s.conversations, activeByMode: s.activeByMode }),
      merge: (persisted, current) => {
        const p = (persisted || {}) as Partial<State>;
        const conversations = Object.fromEntries(
          Object.entries(p.conversations || {}).map(([id, c]) => [
            id,
            {
              ...c,
              // A reload interrupts any stream that was in flight.
              turns: c.turns.map((t) =>
                t.role === "assistant" && (t.phase === "analyzing" || t.phase === "running")
                  ? { ...t, phase: "stopped" as const, tasks: t.tasks.map((k) => (k.status === "grounding" || k.status === "generating" ? { ...k, status: "stopped" as const } : k)) }
                  : t,
              ),
            },
          ]),
        );
        // v0.1 stored a boolean `scene3d`; map it onto the hero mode.
        const legacy = p.settings as (Partial<State["settings"]> & { scene3d?: boolean }) | undefined;
        const settings = { ...DEFAULT_SETTINGS, ...(legacy || {}) };
        if (legacy?.scene3d === false && !legacy.hero) settings.hero = "off";
        delete (settings as { scene3d?: boolean }).scene3d;
        return { ...current, ...p, settings, conversations };
      },
    },
  ),
);

export const agentById = (config: AppConfig | null, id: string) => config?.agents.find((a) => a.id === id);
export const pluginById = (config: AppConfig | null, id?: string | null) => (id ? config?.plugins.find((p) => p.id === id) : undefined);
