// Typed client for the helpdesk API (proxied at /api).

export type Status = "answered" | "pending_approval" | "ticket_created" | "rejected";
export type Priority = "low" | "medium" | "high";
export type Team = "IT" | "HR" | "OPS";

export interface Citation {
  n: number;
  source: string;
  title: string;
  section: string;
}

export interface TicketDraft {
  title: string;
  team: Team;
  priority: Priority;
  description: string;
}

export interface HelpRequest {
  id: number;
  created_at: string;
  channel: string;
  text_masked: string;
  pii_found: string[];
  category: string;
  urgency: Priority;
  team: Team;
  summary: string;
  route: "auto_reply" | "draft_ticket";
  route_reason: string;
  status: Status;
  answer: string | null;
  citations: Citation[];
  retrieval_score: number;
  model: string;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  ticket_draft: TicketDraft | null;
  ticket_key: string | null;
  ticket_url: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
}

export interface AuditEvent {
  at: string;
  step: string;
  detail: Record<string, unknown>;
}

export interface Metrics {
  total: number;
  by_status: Record<Status, number>;
  auto_resolve_rate: number;
  minutes_saved: number;
  minutes_per_auto_answer: number;
  pending: number;
  oldest_pending_minutes: number;
  latency_ms: { avg: number; p95: number };
  tokens: { input: number; output: number };
  cost_usd: number;
  models: string[];
  by_category: { category: string; auto: number; person: number }[];
  per_day: { date: string; count: number }[];
}

export class ApiError extends Error {}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError("Can't reach the helpdesk service. Check that it is running.");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
    throw new ApiError(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  submit: (text: string, requester?: string) =>
    call<HelpRequest>("/requests", { method: "POST", body: JSON.stringify({ text, requester: requester || null }) }),
  list: (status?: Status) => call<HelpRequest[]>(`/requests?limit=200${status ? `&status=${status}` : ""}`),
  audit: (id: number) => call<AuditEvent[]>(`/requests/${id}/audit`),
  approve: (id: number, body: { approver: string; title?: string; team?: Team; priority?: Priority; note?: string }) =>
    call<HelpRequest>(`/requests/${id}/approve`, { method: "POST", body: JSON.stringify(body) }),
  reject: (id: number, approver: string, reason: string) =>
    call<HelpRequest>(`/requests/${id}/reject`, { method: "POST", body: JSON.stringify({ approver, reason }) }),
  metrics: () => call<Metrics>("/metrics"),
};

export const CATEGORY_LABEL: Record<string, string> = {
  it_access: "Access & passwords",
  it_network: "VPN & network",
  it_hardware: "Hardware",
  it_software: "Software",
  it_security: "Security",
  hr_leave: "Leave",
  hr_payroll: "Payroll",
  hr_benefits: "Benefits",
  hr_policy: "Policies",
  other: "Other",
};

export function timeAgo(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}
