export type IntentChannel = "voice" | "text";

export type TaskType =
  | "retrieval"
  | "planning"
  | "coding"
  | "bootstrap"
  | "command"
  | "unknown";

export interface Intent {
  id: string;
  rawInput: string;
  normalizedInput: string;
  channel: IntentChannel;
  taskType: TaskType;
  confidence: number;
  metadata: Record<string, string>;
}

export type ActionKind =
  | "read"
  | "write"
  | "install"
  | "git"
  | "network"
  | "system"
  | "bootstrap"
  | "memory";

export type RiskLevel = "low" | "medium" | "high";

export interface ActionStep {
  id: string;
  title: string;
  description: string;
  kind: ActionKind;
  risk: RiskLevel;
  requiresApproval: boolean;
  command?: string;
  args?: string[];
  workingDirectory?: string;
  dryRunPreview?: string;
}

export interface ApprovalRequest {
  actionId: string;
  reason: string;
  risk: RiskLevel;
  requestedAt: string;
}

export interface ApprovalDecision {
  actionId: string;
  approved: boolean;
  approver: string;
  decidedAt: string;
}

export interface BootstrapSpec {
  projectName: string;
  targetDirectory: string;
  description?: string;
  packageManager: "pnpm";
  stack:
    | "ts-fullstack-default"
    | "frontend-only"
    | "api-only"
    | "custom";
  features: {
    web: boolean;
    api: boolean;
    worker: boolean;
    postgres: boolean;
    redis: boolean;
    docker: boolean;
    githubActions: boolean;
  };
}

export interface WorkspaceContext {
  cwd: string;
  profileRoot: string;
  indexedPaths: string[];
  optOutPaths: string[];
  excludeGlobs: string[];
}

export interface MemoryRecord {
  id: string;
  scope: string;
  content: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface WorkspaceIndexHit {
  path: string;
  relativePath: string;
  modifiedAt: string;
  size: number;
  score: number;
}

export interface ExecutionStepAudit {
  stepId: string;
  status: "pending" | "approved" | "rejected" | "succeeded" | "failed";
  startedAt?: string;
  finishedAt?: string;
  details?: string;
  error?: string;
}

export interface ExecutionAudit {
  runId: string;
  intentId: string;
  plannedAt: string;
  executedAt?: string;
  mode: "dry-run" | "execute";
  status: "planned" | "completed" | "failed" | "blocked";
  approvals: ApprovalDecision[];
  steps: ExecutionStepAudit[];
}

export interface ModelRouteDecision {
  taskType: TaskType;
  complexity: "low" | "medium" | "high";
  route: "local" | "cloud";
  reason: string;
}
