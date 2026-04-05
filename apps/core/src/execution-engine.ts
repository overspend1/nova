import { spawn } from "node:child_process";
import path from "node:path";
import type { ActionStep, ApprovalDecision, ExecutionAudit } from "@nova/contracts";

interface ExecutePlanInput {
  runId: string;
  intentId: string;
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

    if (!isStepCommandAllowed(step, input.allowInstallCommands)) {
      stepAudit.status = "failed";
      stepAudit.finishedAt = new Date().toISOString();
      stepAudit.error = `Command '${step.command ?? "none"}' is not allowed for step kind '${step.kind}'.`;
      stepsAudit.push(stepAudit);
      status = "failed";
      continue;
    }

    try {
      if (step.command) {
        const commandResult = await runCommand(
          step.command,
          step.args ?? [],
          step.workingDirectory
        );
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
  args: string[],
  workingDirectory?: string
): Promise<{ exitCode: number; output: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      shell: false,
      cwd: workingDirectory ? path.resolve(workingDirectory) : undefined,
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

const SAFE_BASE_COMMANDS = new Set([
  "node",
  "npm",
  "pnpm",
  "corepack",
  "git",
  "python",
  "python3"
]);

const SAFE_INSTALL_COMMANDS = new Set(["pnpm", "npm", "corepack"]);
const SAFE_NETWORK_COMMANDS = new Set(["curl", "wget"]);

function isStepCommandAllowed(
  step: ActionStep,
  allowInstallCommands: boolean
): boolean {
  if (!step.command) {
    return true;
  }

  const baseCommand = normalizeCommandName(step.command);

  if (step.kind === "install") {
    return allowInstallCommands && SAFE_INSTALL_COMMANDS.has(baseCommand);
  }

  if (step.kind === "git") {
    return baseCommand === "git";
  }

  if (step.kind === "network") {
    return SAFE_NETWORK_COMMANDS.has(baseCommand);
  }

  return SAFE_BASE_COMMANDS.has(baseCommand);
}

function normalizeCommandName(command: string): string {
  const parsed = path.parse(command.trim().toLowerCase());
  const base = parsed.name || parsed.base;
  return base.replace(/\.exe$/g, "");
}
