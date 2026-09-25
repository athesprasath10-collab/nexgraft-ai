export type AgentId = string;

export interface AgentSpec {
  id: AgentId;
  name: string;
  short_name: string;
  tagline: string;
  description: string;
  color: string;
  icon: string;
  workspace: "chat" | "code" | "research" | "engineering";
  order: number;
  capabilities: string[];
  knowledge_collections: string[];
  user_controls: string[];
  examples: string[];
  tools: string[];
  uses_plugins: boolean;
  boundary: string;
  subtask_title: string;
  subtask_instruction: string;
}

export interface PluginSpec {
  id: string;
  agent: AgentId;
  name: string;
  description: string;
  icon: string;
  knowledge_collection: string;
  tools: string[];
  examples: string[];
  order: number;
}

export interface ToolParam {
  name: string;
  label: string;
  type: "number" | "string" | "text" | "select" | "boolean";
  unit: string;
  default: unknown;
  options: string[] | null;
  required: boolean;
  help: string;
  min: number | null;
  max: number | null;
}

export interface ToolSpec {
  id: string;
  name: string;
  description: string;
  agent: AgentId;
  plugin: string | null;
  category: string;
  formula: string;
  requires_network: boolean;
  params: ToolParam[];
}

export interface ToolOutput {
  summary: string;
  results: { label: string; value: string | number; unit: string }[];
  warnings?: string[];
  notes?: string[];
  alignment?: string;
  protein?: string;
  sequence_preview?: string;
  translation_frame1?: string;
  reverse_complement?: string;
  sources?: Source[];
  records?: ToolOutput[];
  [key: string]: unknown;
}

export interface Language {
  code: string;
  name: string;
  native: string;
  speech: string;
}

export interface AppConfig {
  app_version: string;
  agents: AgentSpec[];
  plugins: PluginSpec[];
  tools: ToolSpec[];
  languages: Language[];
  defaults: {
    model: string | null;
    router: "hybrid" | "heuristic";
    synthesis: boolean;
    literature: boolean;
    num_ctx: number;
    num_predict: number;
    temperature: number;
  };
  features: {
    code_runner: boolean;
    code_timeout: number;
    literature: boolean;
    document_types: string[];
    image_types: string[];
  };
  spline_scene: string | null;
}

export interface ModelInfo {
  name: string;
  size: number;
  family: string;
  parameter_size: string;
  quantization: string;
  capabilities: string[];
  is_embedding: boolean;
  is_vision: boolean;
}

export interface RunningModel {
  name: string;
  size: number;
  size_vram: number;
  gpu_percent: number;
  context_length: number | null;
}

export interface KnowledgeCollection {
  id: string;
  documents: { file: string; title: string; chunks: number; size?: number; error?: string }[];
  chunks: number;
  vectors: boolean;
  indexed_at: number;
}

export interface KnowledgeStats {
  status: string;
  mode: "hybrid" | "keyword";
  embed_model: string;
  embeddings_available: boolean;
  last_error: string | null;
  collections: KnowledgeCollection[];
}

export interface SystemStatus {
  ollama: { reachable: boolean; version: string | null; url: string };
  models: ModelInfo[];
  running: RunningModel[];
  default_model: string | null;
  vision_model: string | null;
  embed_model: { name: string; installed: boolean };
  knowledge: KnowledgeStats;
  model_error?: string;
  settings: { num_ctx: number; num_predict: number; router: string; keep_alive: string; agent_models: Record<string, string> };
}

export interface Attachment {
  id: string;
  kind: "document" | "image";
  name: string;
  size: number;
  chars: number;
  preview?: string;
  model?: string;
  thumb?: string;
}

export interface Source {
  n?: number;
  kind: "knowledge" | "literature";
  title: string;
  snippet?: string;
  // knowledge
  collection?: string;
  doc?: string;
  heading?: string;
  score?: number | null;
  // literature
  authors?: string;
  journal?: string;
  year?: string;
  pmid?: string;
  doi?: string;
  url?: string;
  open_access?: boolean;
  cited_by?: number;
  database?: string;
}

export interface ToolCall {
  tool: string;
  name: string;
  input: Record<string, unknown>;
  output: ToolOutput;
}

export interface GenStats {
  model?: string;
  eval_count?: number;
  prompt_eval_count?: number;
  tokens_per_second?: number | null;
  load_ms?: number;
  wall_ms?: number;
  seconds?: number;
  done_reason?: string;
}

export type TaskStatus = "pending" | "skipped" | "grounding" | "generating" | "done" | "error" | "stopped";

export interface PlanTask {
  id: string;
  agent: AgentId;
  title: string;
  instruction: string;
  search_query: string;
  plugin: string | null;
  agent_name?: string;
  plugin_name?: string | null;
  color?: string;
  enabled?: boolean;
}

export interface TaskRun extends PlanTask {
  status: TaskStatus;
  content: string;
  sources: Source[];
  tools: ToolCall[];
  notes: string[];
  stats?: GenStats;
  error?: string;
  model?: string;
}

export interface Stage {
  stage: string;
  label: string;
  status: "active" | "done";
  detail?: string;
}

export interface Analysis {
  domain: string;
  intent: string;
  capabilities: string[];
  hardware_domain: string | null;
  tasks: PlanTask[];
  complexity: "single" | "multi";
  router: "llm" | "llm+guard" | "heuristic";
  router_notes: string[];
  keyword_scores: Record<string, number>;
  analysis_ms: number;
  analyzer_model: string | null;
  language: { code: string; name: string; native: string; auto: boolean };
  signals: { words: number; documents: number; images: number; sequence_detected: boolean; input_modes: string[] };
  model: string | null;
}

export interface UserTurn {
  id: string;
  role: "user";
  content: string;
  attachments: Attachment[];
  voice?: boolean;
  createdAt: number;
}

export type TurnPhase = "analyzing" | "awaiting" | "running" | "done" | "error" | "stopped";

export interface AssistantTurn {
  id: string;
  role: "assistant";
  mode: "orchestrator" | "direct";
  phase: TurnPhase;
  stages: Stage[];
  analysis?: Analysis;
  tasks: TaskRun[];
  synthesis?: TaskRun;
  error?: string;
  seconds?: number;
  createdAt: number;
}

export type Turn = UserTurn | AssistantTurn;

export interface Conversation {
  id: string;
  title: string;
  mode: "orchestrator" | AgentId;
  plugin?: string | null;
  createdAt: number;
  updatedAt: number;
  turns: Turn[];
}

export interface Settings {
  model: string | null;
  agentModels: Record<string, string>;
  router: "hybrid" | "heuristic";
  autoRun: boolean;
  synthesis: boolean;
  literature: boolean;
  useKnowledge: boolean;
  language: string;
  numCtx: number | null;
  numPredict: number | null;
  temperature: number | null;
  scene3d: boolean;
  theme: "dark" | "light";
}

export interface RunResult {
  exit_code: number | null;
  timed_out: boolean;
  stdout: string;
  stderr: string;
  seconds: number;
  python: string;
  artifacts: { name: string; type: "image" | "text" | "file"; size: number; data_url?: string; preview?: string }[];
}

export interface GraphStructure {
  nodes: string[];
  edges: { source: string; target: string; conditional: boolean }[];
  mermaid: string;
}
