import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../../apps/core/src/server.js";
import type { NovaCoreConfig } from "../../apps/core/src/config.js";
import type { ActionStep } from "@nova/contracts";

describe("voice -> plan -> approval -> execute -> audit", () => {
  let tempDir: string;
  let app: Awaited<ReturnType<typeof buildServer>>["app"];

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "nova-e2e-test-"));
    const config: NovaCoreConfig = {
      pipePath: "\\\\.\\pipe\\nova-e2e-test",
      authToken: "e2e-token-123456",
      profileRoot: tempDir,
      auditFilePath: path.join(tempDir, "audit", "timeline.jsonl"),
      memoryRootPath: path.join(tempDir, "memory"),
      allowInstallCommands: false,
      authMinTokenLength: 16
    };
    app = (await buildServer(config)).app;
  });

  afterEach(async () => {
    await app.close();
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("runs a full approval-gated execution flow", async () => {
    const planResponse = await app.inject({
      method: "POST",
      url: "/actions/plan",
      headers: {
        "x-nova-token": "e2e-token-123456"
      },
      payload: {
        input: "Refactor this module safely and run validation",
        channel: "voice"
      }
    });
    expect(planResponse.statusCode).toBe(200);
    const planBody = planResponse.json() as { steps: ActionStep[]; intent: { id: string } };
    const approvals = planBody.steps
      .filter((step) => step.requiresApproval)
      .map((step) => ({
        actionId: step.id,
        approved: true,
        approver: "e2e-user"
      }));

    const executeResponse = await app.inject({
      method: "POST",
      url: "/actions/execute",
      headers: {
        "x-nova-token": "e2e-token-123456"
      },
      payload: {
        mode: "execute",
        intent: planBody.intent,
        steps: planBody.steps,
        approvals
      }
    });
    expect(executeResponse.statusCode).toBe(200);
    const executeBody = executeResponse.json();
    expect(["completed", "failed"]).toContain(executeBody.audit.status);

    const auditResponse = await app.inject({
      method: "GET",
      url: "/audit/timeline",
      headers: { "x-nova-token": "e2e-token-123456" }
    });
    expect(auditResponse.statusCode).toBe(200);
    const timeline = auditResponse.json() as Array<{ intentId: string }>;
    expect(timeline.length).toBeGreaterThan(0);
  });
});
