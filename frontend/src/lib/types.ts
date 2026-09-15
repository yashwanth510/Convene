export interface User {
  id: string;
  email: string;
}
export interface Model {
  id: string;
  name: string;
  provider: string;
  status: string;
  available: boolean;
  configured: boolean;
  last_status: string;
}
export interface Source {
  id: string;
  title: string;
  url: string | null;
  content: string;
  kind: string;
}
export interface Claim {
  claim: string;
  status: string;
  source_id: string | null;
  excerpt: string;
  note: string;
}
export interface Position {
  id: string;
  model_id: string;
  model_name: string;
  actual_model: string;
  content: string;
}
export interface Result {
  run_id?: string;
  content: string;
  mode?: string;
  status?: string;
  notice?: string;
  sources?: Source[];
  positions?: Position[];
  warnings?: string[];
  rounds?: {
    round: number;
    agreement: number;
    reviewers: number;
    feedback: string[];
  }[];
  evidence?: { status: string; claims: Claim[]; note?: string };
  usage?: {
    calls: number;
    total_tokens: number;
    estimated_tokens: boolean;
    reported_cost_usd: number | null;
  };
  duration_seconds?: number;
}
export interface Message {
  id: string;
  role: string;
  content: string;
  timestamp: string;
  result?: Result | null;
}
export interface ConversationSummary {
  id: string;
  title: string;
  updated_at?: string;
  active_run_id?: string | null;
}
export interface Conversation extends ConversationSummary {
  messages: Message[];
}
export interface Run {
  id: string;
  conversation_id: string;
  status: string;
  result?: Result;
  event_seq?: number;
}
export interface Settings {
  mode: "auto" | "fast" | "council";
  panel_size: number;
  debate_rounds: number;
  web_search_enabled: boolean;
  enabled_models: string[];
}
export interface Document {
  name: string;
  text: string;
  truncated?: boolean;
}
