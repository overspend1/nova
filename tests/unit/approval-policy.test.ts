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
});

