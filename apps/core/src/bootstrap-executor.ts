import fs from "node:fs/promises";
import path from "node:path";
import type { ApprovalDecision, ExecutionAudit } from "@nova/contracts";
import { executePlan } from "./execution-engine.js";
import type { NovaCoreConfig } from "./config.js";
import {
  inferBootstrapSpecFromBrief,
  materializeBootstrapFiles,
  planBootstrapActions
} from "@nova/bootstrap";
import { nanoid } from "nanoid";

interface BootstrapExecutionInput {
  brief: string;
  targetDirectory: string;
  mode: "dry-run" | "execute";
  approver: string;
  approvedActionIds: string[];
  config: NovaCoreConfig;
}

export async function runBootstrap(input: BootstrapExecutionInput): Promise<{
  projectRoot: string;
  filesWritten: number;
  spec: ReturnType<typeof inferBootstrapSpecFromBrief>;
  audit: ExecutionAudit;
}> {
  const spec = inferBootstrapSpecFromBrief(input.brief, input.targetDirectory);
  const steps = planBootstrapActions(spec);
  const approvals: ApprovalDecision[] = steps.map((step) => ({
    actionId: step.id,
    approved: input.approvedActionIds.includes(step.id),
    approver: input.approver,
    decidedAt: new Date().toISOString()
  }));

  const audit = await executePlan({
    runId: `run_${nanoid()}`,
    intentId: `intent_bootstrap_${nanoid(8)}`,
    requestId: `req_${nanoid(10)}`,
    idempotencyKey: `bootstrap:${spec.targetDirectory}:${spec.projectName}:${input.mode}`,
    steps,
    approvals,
    mode: input.mode,
    allowInstallCommands: input.config.allowInstallCommands
  });

  const projectRoot = path.join(spec.targetDirectory, spec.projectName);
  let filesWritten = 0;
  const approvalSet = new Set(input.approvedActionIds);
  const writeApproved =
    approvalSet.has("bootstrap-create-root") && approvalSet.has("bootstrap-write-files");

  if (input.mode === "execute" && writeApproved) {
    const files = materializeBootstrapFiles(spec);
    for (const [relativePath, content] of Object.entries(files)) {
      const absolutePath = path.join(spec.targetDirectory, relativePath);
      await fs.mkdir(path.dirname(absolutePath), { recursive: true });
      await fs.writeFile(absolutePath, content, "utf-8");
      filesWritten += 1;
    }
  }

  return {
    projectRoot,
    filesWritten,
    spec,
    audit
  };
}
