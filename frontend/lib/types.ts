export type Severity = "critical" | "high" | "medium" | "low" | "info";
export type MissionStatus = "queued" | "running" | "completed" | "failed" | "blocked";

export interface MissionSummary {
  id: string;
  title: string;
  repository: string;
  status: MissionStatus;
  outcome: string;
  progress: number;
  summary: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  duration_ms: number;
  error: string;
}

export interface MissionStep {
  stage: string;
  name: string;
  status: string;
  message: string;
  order_index: number;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface AgentRun {
  agent: string;
  role: string;
  status: string;
  summary: string;
  result: Record<string, unknown>;
  findings: Finding[];
  evidence: Evidence[];
  affected_files: string[];
  recommendations: string[];
  confidence: number;
  duration_ms: number;
  order_index: number;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface Finding {
  id?: number;
  agent: string;
  title: string;
  detail: string;
  severity: Severity;
  category: string;
  file: string;
  line?: number | null;
  confidence: number;
  evidence_refs: string[];
}

export interface Evidence {
  id?: number;
  agent: string;
  kind: string;
  label: string;
  source: string;
  payload: Record<string, unknown>;
}

export interface MissionDetail extends MissionSummary {
  mission_text: string;
  seed: number;
  steps: MissionStep[];
  agents: AgentRun[];
  gate_overall: string;
}

export interface CodeChange {
  id?: number;
  path: string;
  status: string;
  added: number;
  removed: number;
  diff: string;
  reason: string;
}

export interface TestResult {
  id?: number;
  suite: string;
  phase: string;
  path: string;
  name: string;
  status: string;
  duration_ms: number;
  detail: string;
}

export interface SecurityFinding {
  id?: number;
  rule: string;
  severity: Severity;
  title: string;
  path: string;
  line?: number | null;
  description: string;
  remediation: string;
}

export interface Review {
  id?: number;
  reviewer: string;
  verdict: string;
  score: number;
  summary: string;
  issues: Record<string, unknown>[];
  reviewed_files: string[];
}

export interface ReleaseGate {
  name: string;
  status: string;
  detail: string;
  order_index: number;
  checked_at?: string | null;
}

export interface Metric {
  key: string;
  label: string;
  value: number;
  unit: string;
  source: string;
  order_index: number;
}

export interface AuditEvent {
  agent: string;
  category: string;
  message: string;
  at: string;
}

export interface EvidenceGraphNode {
  id: string;
  label: string;
  kind: string;
  status: string;
  count: number;
  detail: string;
}

export interface EvidenceGraphEdge {
  source: string;
  target: string;
  kind: string;
}

export interface RepositoryIndex {
  name: string;
  path: string;
  stats: Record<string, unknown>;
  files: unknown[];
  tests: unknown[];
  architecture: { components: unknown[]; edges: unknown[] };
  dependencies: unknown[];
  source?: { owner: string; repo: string; branch: string; html_url: string };
}

export interface Skill {
  id: string;
  name: string;
  description: string;
  keywords: string[];
  detect_signals: number;
  observations: number;
  patches: string[];
  regression_dest: string;
  matched?: boolean;
}

export interface MissionReport {
  mission: MissionSummary;
  summary: string;
  repository: RepositoryIndex;
  root_cause: Finding | null;
  planning: Finding[];
  findings: Finding[];
  evidence: Evidence[];
  code_changes: CodeChange[];
  tests: TestResult[];
  security: SecurityFinding[];
  security_scan: Record<Severity, number>;
  reviews: Review[];
  release_gate: { checks: ReleaseGate[]; overall: string };
  metrics: Metric[];
  activity: AuditEvent[];
  evidence_graph: { nodes: EvidenceGraphNode[]; edges: EvidenceGraphEdge[] };
  skills: Skill[];
  workflow_time_ms: number;
  baseline_minutes: number;
}