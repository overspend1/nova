from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


IntentChannel = Literal["voice", "text"]
TaskType = Literal["retrieval", "planning", "coding", "bootstrap", "command", "unknown"]
ActionKind = Literal[
    "read",
    "write",
    "install",
    "git",
    "network",
    "system",
    "bootstrap",
    "memory",
]
RiskLevel = Literal["low", "medium", "high"]
RouteTarget = Literal["local", "cloud"]
Complexity = Literal["low", "medium", "high"]
ExecutionMode = Literal["dry-run", "execute"]
ExecutionStatus = Literal["planned", "completed", "failed", "blocked"]
ExecutionStepStatus = Literal["pending", "approved", "rejected", "succeeded", "failed"]
TaskPriority = Literal["low", "normal", "high", "critical"]
TaskStatus = Literal[
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
]


class Intent(BaseModel):
    id: str
    rawInput: str
    normalizedInput: str
    channel: IntentChannel
    taskType: TaskType
    confidence: float
    metadata: dict[str, str] = Field(default_factory=dict)


class ActionStep(BaseModel):
    id: str
    title: str
    description: str
    kind: ActionKind
    risk: RiskLevel
    requiresApproval: bool
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    workingDirectory: str | None = None
    dryRunPreview: str | None = None
    toolName: str | None = None
    toolArgs: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    actionId: str
    reason: str
    risk: RiskLevel
    requestedAt: str


class ApprovalDecision(BaseModel):
    actionId: str
    approved: bool
    approver: str
    decidedAt: str


class BootstrapFeatures(BaseModel):
    web: bool
    api: bool
    worker: bool
    postgres: bool
    redis: bool
    docker: bool
    githubActions: bool


class BootstrapSpec(BaseModel):
    projectName: str
    targetDirectory: str
    description: str | None = None
    packageManager: Literal["pnpm"] = "pnpm"
    stack: Literal["ts-fullstack-default", "frontend-only", "api-only", "custom"] = (
        "ts-fullstack-default"
    )
    features: BootstrapFeatures


class WorkspaceContext(BaseModel):
    cwd: str
    profileRoot: str
    indexedPaths: list[str] = Field(default_factory=list)
    optOutPaths: list[str] = Field(default_factory=list)
    excludeGlobs: list[str] = Field(default_factory=list)


class MemoryRecord(BaseModel):
    id: str
    scope: str
    content: str
    tags: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class WorkspaceIndexHit(BaseModel):
    path: str
    relativePath: str
    modifiedAt: str
    size: int
    score: int = 0


class ExecutionStepAudit(BaseModel):
    stepId: str
    status: ExecutionStepStatus
    startedAt: str | None = None
    finishedAt: str | None = None
    details: str | None = None
    error: str | None = None


class ExecutionAudit(BaseModel):
    runId: str
    intentId: str
    plannedAt: str
    executedAt: str | None = None
    mode: ExecutionMode
    status: ExecutionStatus
    approvals: list[ApprovalDecision] = Field(default_factory=list)
    steps: list[ExecutionStepAudit] = Field(default_factory=list)


class ModelRouteDecision(BaseModel):
    taskType: TaskType
    complexity: Complexity
    route: RouteTarget
    reason: str


class IntentParseRequest(BaseModel):
    input: str
    channel: IntentChannel = "text"
    metadata: dict[str, str] = Field(default_factory=dict)


class ActionsPlanRequest(BaseModel):
    input: str
    channel: IntentChannel = "text"
    metadata: dict[str, str] = Field(default_factory=dict)


class ActionsExecuteRequest(BaseModel):
    mode: ExecutionMode = "execute"
    input: str | None = None
    channel: IntentChannel = "text"
    intent: Intent | None = None
    steps: list[ActionStep] | None = None
    approvals: list[ApprovalDecision] = Field(default_factory=list)


class BootstrapCreateRequest(BaseModel):
    brief: str
    targetDirectory: str | None = None
    mode: ExecutionMode = "dry-run"
    approvedActionIds: list[str] = Field(default_factory=list)
    approver: str = "user"


class MemoryUpsertRequest(BaseModel):
    id: str | None = None
    scope: str
    content: str
    tags: list[str] = Field(default_factory=list)


class MemorySearchRequest(BaseModel):
    query: str
    scope: str | None = None
    limit: int = 10
    workspaceLimit: int = 10
    includeWorkspaceHits: bool = True
    refreshIndex: bool = False
    indexedPaths: list[str] | None = None
    optOutPaths: list[str] | None = None
    maxFiles: int | None = None


class MemoryContextRequest(BaseModel):
    indexedPaths: list[str] | None = None
    optOutPaths: list[str] | None = None
    profileRoot: str | None = None
    reindex: bool = False
    maxFiles: int | None = None


class AssistantRespondRequest(BaseModel):
    input: str
    channel: IntentChannel = "text"
    includePlan: bool = True
    metadata: dict[str, str] = Field(default_factory=dict)


class AgentTaskCreateRequest(BaseModel):
    prompt: str
    channel: IntentChannel = "text"
    metadata: dict[str, str] = Field(default_factory=dict)
    mode: ExecutionMode = "dry-run"
    priority: TaskPriority = "normal"
    approvals: list[ApprovalDecision] = Field(default_factory=list)
    maxSteps: int = 8
    allowReplan: bool = True


class AgentTaskApproveRequest(BaseModel):
    approvals: list[ApprovalDecision]
    mode: ExecutionMode = "execute"


class AgentTaskRecord(BaseModel):
    id: str
    prompt: str
    channel: IntentChannel
    metadata: dict[str, str] = Field(default_factory=dict)
    mode: ExecutionMode
    priority: TaskPriority
    status: TaskStatus
    createdAt: str
    updatedAt: str
    logs: list[str] = Field(default_factory=list)
    intent: Intent | None = None
    route: ModelRouteDecision | None = None
    steps: list[ActionStep] = Field(default_factory=list)
    approvalRequests: list[ApprovalRequest] = Field(default_factory=list)
    approvals: list[ApprovalDecision] = Field(default_factory=list)
    audit: ExecutionAudit | None = None
    assistantSummary: str | None = None
    error: str | None = None
