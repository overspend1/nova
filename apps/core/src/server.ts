import os from "node:os";
import path from "node:path";
import Fastify, { type FastifyInstance } from "fastify";
import { nanoid } from "nanoid";
import type {
  ActionStep,
  ApprovalDecision,
  ExecutionAudit,
  Intent,
  IntentChannel,
  MemoryRecord
} from "@nova/contracts";
import { MemoryStore } from "@nova/memory";
import { parseIntent } from "./intent-parser.js";
import { routeModel } from "./model-router.js";
import { createActionPlan } from "./action-planner.js";
import { executePlan } from "./execution-engine.js";
import { AuditLog } from "./audit-log.js";
import { loadConfig, type NovaCoreConfig } from "./config.js";
import { runBootstrap } from "./bootstrap-executor.js";

interface ServerBundle {
  app: FastifyInstance;
  config: NovaCoreConfig;
}

const EXECUTION_CACHE_TTL_MS = 5 * 60 * 1000;

export async function buildServer(
  config: NovaCoreConfig = loadConfig()
): Promise<ServerBundle> {
  const app = Fastify({
    logger: true
  });
  const auditLog = new AuditLog(config.auditFilePath);
  const memory = new MemoryStore(config.memoryRootPath);
  const executionReplayCache = new Map<
    string,
    {
      createdAt: number;
      response: {
        intent: Intent;
        steps: ActionStep[];
        audit: ExecutionAudit;
      };
    }
  >();
  await memory.getWorkspaceContext(config.profileRoot);

  app.addHook("preHandler", async (request, reply) => {
    if (request.url.startsWith("/health")) {
      return;
    }

    const token = request.headers["x-nova-token"];
    if (
      typeof token !== "string" ||
      token.length < config.authMinTokenLength ||
      token !== config.authToken
    ) {
      reply.code(401);
      throw new Error("Unauthorized request.");
    }
  });

  app.get("/health", async () => {
    return {
      ok: true,
      pipePath: config.pipePath,
      profileRoot: config.profileRoot
    };
  });

  app.get("/audit/timeline", async (request) => {
    const query = request.query as { limit?: number };
    return auditLog.list(query.limit ?? 100);
  });

  app.post("/intent/parse", async (request) => {
    const body = request.body as {
      input: string;
      channel?: IntentChannel;
      metadata?: Record<string, string>;
    };

    const intent = parseIntent({
      text: body.input,
      channel: body.channel,
      metadata: body.metadata
    });
    const route = routeModel(intent);
    return { intent, route };
  });

  app.post("/actions/plan", async (request) => {
    const body = request.body as {
      input: string;
      channel?: IntentChannel;
      metadata?: Record<string, string>;
    };

    const input = typeof body.input === "string" ? body.input.trim() : "";
    if (!input) {
      throw new Error("Plan input is required.");
    }

    const intent = parseIntent({
      text: input,
      channel: body.channel,
      metadata: body.metadata
    });
    const route = routeModel(intent);
    const steps = createActionPlan(intent);

    const runId = `run_${nanoid()}`;
    const audit: ExecutionAudit = {
      runId,
      intentId: intent.id,
      plannedAt: new Date().toISOString(),
      mode: "dry-run",
      status: "planned",
      approvals: [] as ApprovalDecision[],
      steps: steps.map((step) => ({
        stepId: step.id,
        status: "pending" as const
      }))
    };
    await auditLog.append(audit);

    return {
      runId,
      intent,
      route,
      steps,
      audit
    };
  });

  app.post("/actions/execute", async (request) => {
    const body = request.body as {
      mode?: "dry-run" | "execute";
      input?: string;
      channel?: IntentChannel;
      intent?: Intent;
      steps?: ActionStep[];
      approvals?: Array<{ actionId: string; approved: boolean; approver?: string }>;
    };
    const idempotencyKeyHeader = request.headers["x-nova-idempotency-key"];
    const requestIdHeader = request.headers["x-nova-request-id"];
    const idempotencyKey =
      typeof idempotencyKeyHeader === "string" && idempotencyKeyHeader.trim().length > 0
        ? idempotencyKeyHeader.trim()
        : undefined;
    const requestId =
      typeof requestIdHeader === "string" && requestIdHeader.trim().length > 0
        ? requestIdHeader.trim()
        : undefined;

    const now = Date.now();
    for (const [key, value] of executionReplayCache.entries()) {
      if (now - value.createdAt > EXECUTION_CACHE_TTL_MS) {
        executionReplayCache.delete(key);
      }
    }
    if (idempotencyKey) {
      const cached = executionReplayCache.get(idempotencyKey);
      if (cached) {
        return cached.response;
      }
    }

    const mode = body.mode ?? "execute";
    if (!body.intent && (!body.input || typeof body.input !== "string" || body.input.trim().length === 0)) {
      throw new Error("Execution requires either a valid intent or non-empty input.");
    }
    const intent =
      body.intent ??
      parseIntent({
        text: body.input?.trim() ?? "",
        channel: body.channel ?? "text"
      });
    const steps = body.steps ?? createActionPlan(intent);
    if (!Array.isArray(steps) || steps.length === 0) {
      throw new Error("Execution requires at least one action step.");
    }
    const approvals: ApprovalDecision[] = (body.approvals ?? []).map((decision) => ({
      actionId: decision.actionId,
      approved: decision.approved,
      approver: decision.approver ?? "user",
      decidedAt: new Date().toISOString()
    }));

    const audit = await executePlan({
      runId: `run_${nanoid()}`,
      intentId: intent.id,
      requestId,
      idempotencyKey,
      mode,
      steps,
      approvals,
      allowInstallCommands: config.allowInstallCommands
    });
    await auditLog.append(audit);
    const response = { intent, steps, audit };
    if (idempotencyKey) {
      executionReplayCache.set(idempotencyKey, {
        createdAt: now,
        response
      });
    }
    return response;
  });

  app.post("/bootstrap/create", async (request) => {
    const body = request.body as {
      brief: string;
      targetDirectory?: string;
      mode?: "dry-run" | "execute";
      approvedActionIds?: string[];
      approver?: string;
    };
    const targetDirectory = body.targetDirectory ?? process.cwd();
    const mode = body.mode ?? "dry-run";

    const result = await runBootstrap({
      brief: body.brief,
      targetDirectory,
      mode,
      approver: body.approver ?? "user",
      approvedActionIds: body.approvedActionIds ?? [],
      config
    });
    await auditLog.append(result.audit);

    return {
      projectRoot: result.projectRoot,
      filesWritten: result.filesWritten,
      spec: result.spec,
      audit: result.audit
    };
  });

  app.post("/memory/upsert", async (request) => {
    const body = request.body as Partial<MemoryRecord> & {
      id?: string;
      scope: string;
      content: string;
      tags?: string[];
    };
    const id = body.id ?? `mem_${nanoid(12)}`;
    const now = new Date().toISOString();
    const record = await memory.upsert({
      id,
      scope: body.scope,
      content: body.content,
      tags: body.tags ?? [],
      createdAt: body.createdAt ?? now,
      updatedAt: now
    });
    return { record };
  });

  app.post("/memory/search", async (request) => {
    const body = request.body as {
      query: string;
      scope?: string;
      limit?: number;
    };
    const records = await memory.search(body.query, body.scope, body.limit ?? 10);
    const workspaceContext = await memory.getWorkspaceContext(config.profileRoot);
    return {
      records,
      workspaceContext
    };
  });

  app.post("/memory/context", async (request) => {
    const body = request.body as {
      indexedPaths?: string[];
      optOutPaths?: string[];
      profileRoot?: string;
    };
    const context = await memory.saveWorkspaceContext({
      profileRoot: body.profileRoot ?? os.homedir(),
      indexedPaths: body.indexedPaths ?? [path.resolve(config.profileRoot)],
      optOutPaths: body.optOutPaths ?? []
    });
    return { context };
  });

  return {
    app,
    config
  };
}
