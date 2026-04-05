import { spawn } from "node:child_process";
import type { ActionStep, ApprovalDecision, ExecutionAudit } from "@nova/contracts";

interface ExecutePlanInput {
  runId: string;
  intentId: string;
  requestId?: string;
  idempotencyKey?: string;
  mode: "dry-run" | "execute";
  steps: ActionStep[];
  approvals: ApprovalDecision[];
  allowInstallCommands: boolean;
}

export async function executePlan(input: ExecutePlanInput): Promise<ExecutionAudit> {
  const approvalMap = new Map(input.approvals.map((decision) => [decision.actionId, decision]));
  const stepsAudit: ExecutionAudit["steps"] = [];
  let status: ExecutionAudit["status"] = "completed";

  for (const step of input.steps) {
    const stepAudit: ExecutionAudit["steps"][number] = {
      stepId: step.id,
      status: "pending",
      startedAt: new Date().toISOString()
    };

    if (step.requiresApproval) {
      const decision = approvalMap.get(step.id);
      if (!decision?.approved) {
        stepAudit.status = "rejected";
        stepAudit.finishedAt = new Date().toISOString();
        stepAudit.details = "Blocked: explicit approval missing.";
        stepsAudit.push(stepAudit);
        status = "blocked";
        continue;
      }
      stepAudit.status = "approved";
    }

    if (input.mode === "dry-run") {
      stepAudit.status = "succeeded";
      stepAudit.finishedAt = new Date().toISOString();
      stepAudit.details = step.dryRunPreview ?? "Dry run completed.";
      stepsAudit.push(stepAudit);
      continue;
    }

    if (step.kind === "install" && !input.allowInstallCommands) {
      stepAudit.status = "failed";
      stepAudit.finishedAt = new Date().toISOString();
      stepAudit.error = "Install commands are disabled by NOVA_ALLOW_INSTALL_COMMANDS.";
      stepsAudit.push(stepAudit);
      status = "failed";
      continue;
    }

    try {
      if (step.command) {
        const commandResult = await runCommand(step.command, step.args ?? []);
        stepAudit.status = commandResult.exitCode === 0 ? "succeeded" : "failed";
        stepAudit.details = commandResult.output;
        stepAudit.error =
          commandResult.exitCode === 0
            ? undefined
            : `Command exited with code ${commandResult.exitCode}.`;
      } else {
        stepAudit.status = "succeeded";
        stepAudit.details = "No command to execute; step acknowledged.";
      }

      if (stepAudit.status === "failed") {
        status = "failed";
      }
    } catch (error) {
      stepAudit.status = "failed";
      stepAudit.error = error instanceof Error ? error.message : "Unknown execution error.";
      status = "failed";
    }

    stepAudit.finishedAt = new Date().toISOString();
    stepsAudit.push(stepAudit);
  }

  return {
    runId: input.runId,
    intentId: input.intentId,
    requestId: input.requestId,
    idempotencyKey: input.idempotencyKey,
    plannedAt: new Date().toISOString(),
    executedAt: new Date().toISOString(),
    mode: input.mode,
    status,
    approvals: input.approvals,
    steps: stepsAudit
  };
}

function runCommand(
  command: string,
  args: string[]
): Promise<{ exitCode: number; output: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      shell: false,
      stdio: ["ignore", "pipe", "pipe"]
    });

    let output = "";
    child.stdout.on("data", (chunk) => {
      output += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      output += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      resolve({ exitCode: code ?? 1, output: output.trim() });
    });
  });
}
