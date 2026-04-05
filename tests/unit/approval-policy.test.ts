import { describe, expect, it } from "vitest";
import { executePlan } from "../../apps/core/src/execution-engine.js";
import type { ActionStep } from "@nova/contracts";

const mutatingStep: ActionStep = {
  id: "write_1",
  title: "Write file",
  description: "Mutate files",
  kind: "write",
  risk: "high",
  requiresApproval: true,
  command: "node",
  args: ["-v"]
};

describe("approval policy", () => {
  it("blocks mutating step without approval", async () => {
    const audit = await executePlan({
      runId: "run_1",
      intentId: "intent_1",
      mode: "execute",
      steps: [mutatingStep],
      approvals: [],
      allowInstallCommands: true
    });

    expect(audit.status).toBe("blocked");
    expect(audit.steps[0].status).toBe("rejected");
  });

  it("executes approved step", async () => {
    const audit = await executePlan({
      runId: "run_2",
      intentId: "intent_2",
      mode: "execute",
      steps: [mutatingStep],
      approvals: [
        {
          actionId: "write_1",
          approved: true,
          approver: "tester",
          decidedAt: new Date().toISOString()
        }
      ],
      allowInstallCommands: true
    });

    expect(["completed", "failed"]).toContain(audit.status);
    expect(["succeeded", "failed"]).toContain(audit.steps[0].status);
  });

  it("blocks disallowed network command", async () => {
    const audit = await executePlan({
      runId: "run_3",
      intentId: "intent_3",
      mode: "execute",
      steps: [
        {
          id: "net_1",
          title: "Network command",
          description: "Run disallowed command",
          kind: "network",
          risk: "high",
          requiresApproval: true,
          command: "powershell",
          args: ["-Command", "Write-Host hi"]
        }
      ],
      approvals: [
        {
          actionId: "net_1",
          approved: true,
          approver: "tester",
          decidedAt: new Date().toISOString()
        }
      ],
      allowInstallCommands: true
    });

    expect(audit.status).toBe("failed");
    expect(audit.steps[0].status).toBe("failed");
    expect(audit.steps[0].error).toContain("not allowed");
  });

  it("blocks install command when disabled by config", async () => {
    const audit = await executePlan({
      runId: "run_4",
      intentId: "intent_4",
      mode: "execute",
      steps: [
        {
          id: "install_1",
          title: "Install deps",
          description: "Install dependencies",
          kind: "install",
          risk: "high",
          requiresApproval: true,
          command: "pnpm",
          args: ["install"]
        }
      ],
      approvals: [
        {
          actionId: "install_1",
          approved: true,
          approver: "tester",
          decidedAt: new Date().toISOString()
        }
      ],
      allowInstallCommands: false
    });

    expect(audit.status).toBe("failed");
    expect(audit.steps[0].status).toBe("failed");
    expect(audit.steps[0].error).toContain("disabled");
  });
});

