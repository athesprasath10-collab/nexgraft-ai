import type {
  AppConfig,
  Attachment,
  GraphStructure,
  KnowledgeStats,
  PlanTask,
  RunResult,
  Settings,
  SystemStatus,
  ToolOutput,
  ToolSpec,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new ApiError("Cannot reach the NEXGRAFT server. Is `python run.py` running?", 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not JSON */
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  config: () => request<AppConfig>("/api/config"),
  status: () => request<SystemStatus>("/api/status"),
  graph: () => request<Record<"analysis" | "execution", GraphStructure>>("/api/graph"),
  tools: (agent?: string, plugin?: string | null) => {
    const q = new URLSearchParams();
    if (agent) q.set("agent", agent);
    if (plugin) q.set("plugin", plugin);
    return request<ToolSpec[]>(`/api/tools?${q}`);
  },
  runTool: (id: string, params: Record<string, unknown>) =>
    request<{ tool: string; name: string; output: ToolOutput; ms: number }>(`/api/tools/${id}`, json({ params })),
  execute: (code: string, attachments: string[]) => request<RunResult>("/api/execute", json({ code, attachments })),
  upload: (file: File, hint = "") => {
    const form = new FormData();
    form.append("file", file);
    form.append("hint", hint);
    return request<Attachment>("/api/attachments", { method: "POST", body: form });
  },
  knowledge: () => request<KnowledgeStats>("/api/knowledge"),
  reindex: (collection?: string) =>
    request<KnowledgeStats>(`/api/knowledge/reindex${collection ? `?collection=${encodeURIComponent(collection)}` : ""}`, { method: "POST" }),
  createCollection: (id: string) => request<KnowledgeStats>("/api/knowledge/collections", json({ id })),
  uploadKnowledge: (collection: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<KnowledgeStats>(`/api/knowledge/${encodeURIComponent(collection)}/upload`, { method: "POST", body: form });
  },
  deleteKnowledge: (collection: string, file: string) =>
    request<KnowledgeStats>(`/api/knowledge/${encodeURIComponent(collection)}/${encodeURIComponent(file)}`, { method: "DELETE" }),
};

export function requestOptions(s: Settings, voice = false) {
  const opts: Record<string, unknown> = {
    router: s.router,
    language: s.language,
    synthesis: s.synthesis,
    literature: s.literature,
    use_knowledge: s.useKnowledge,
    voice,
  };
  if (s.model) opts.model = s.model;
  const agentModels = Object.fromEntries(Object.entries(s.agentModels).filter(([, v]) => v));
  if (Object.keys(agentModels).length) opts.agent_models = agentModels;
  if (s.numCtx) opts.num_ctx = s.numCtx;
  if (s.numPredict) opts.num_predict = s.numPredict;
  if (s.temperature !== null && s.temperature !== undefined) opts.temperature = s.temperature;
  return opts;
}

export type StreamEvent = { type: string; [key: string]: any }; // eslint-disable-line @typescript-eslint/no-explicit-any

/** POSTs JSON and yields newline-delimited JSON events as they stream in. */
export async function* streamEvents(path: string, body: unknown, signal: AbortSignal): AsyncGenerator<StreamEvent> {
  let res: Response;
  try {
    res = await fetch(path, { ...json(body), signal });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Cannot reach the NEXGRAFT server. Is `python run.py` running?", 0);
  }
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const b = await res.json();
      detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let nl: number;
    while ((nl = buffer.indexOf("\n")) >= 0) {
      const line = buffer.slice(0, nl).trim();
      buffer = buffer.slice(nl + 1);
      if (line) yield JSON.parse(line) as StreamEvent;
    }
  }
  if (buffer.trim()) yield JSON.parse(buffer) as StreamEvent;
}

export interface RunBody {
  message: string;
  history: { role: "user" | "assistant"; content: string }[];
  attachments: string[];
  tasks?: PlanTask[];
  agent?: string;
  plugin?: string | null;
  options: Record<string, unknown>;
}
