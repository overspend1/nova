import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../../apps/core/src/server.js";
import type { NovaCoreConfig } from "../../apps/core/src/config.js";
import type { ActionStep } from "@nova/contracts";

describe("execution idempotency", () => {
  let tempDir: string;
  let app: Awaited<ReturnType<typeof buildServer>>["app"];

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "nova-idempotency-test-"));
    const config: NovaCoreConfig = {
      pipePath: "\\\\.\\pipe\\nova-idempotency-test",
      authToken: "idempotency-token-123456",
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

  it("returns cached execution response for same idempotency key", async () => {
    const steps: ActionStep[] = [
      {
        id: "step_demo",
        title: "Demo",
        description: "demo",
        kind: "read",
        risk: "low",
        requiresApproval: false
      }
    ];

    const payload = {
      mode: "dry-run",
      input: "Summarize the repository",
      channel: "text",
      steps
    };
    const headers = {
      "x-nova-token": "idempotency-token-123456",
      "x-nova-idempotency-key": "idem-1",
      "x-nova-request-id": "req-1"
    };

    const first = await app.inject({
      method: "POST",
      url: "/actions/execute",
      headers,
      payload
    });
    expect(first.statusCode).toBe(200);
    const firstBody = first.json() as { audit: { runId: string } };

    const second = await app.inject({
      method: "POST",
      url: "/actions/execute",
      headers: {
        ...headers,
        "x-nova-request-id": "req-2"
      },
      payload
    });
    expect(second.statusCode).toBe(200);
    const secondBody = second.json() as { audit: { runId: string } };

    expect(secondBody.audit.runId).toBe(firstBody.audit.runId);

    const timeline = await app.inject({
      method: "GET",
      url: "/audit/timeline",
      headers: { "x-nova-token": "idempotency-token-123456" }
    });
    expect(timeline.statusCode).toBe(200);
    const timelineBody = timeline.json() as Array<{ runId: string }>;
    expect(timelineBody.filter((entry) => entry.runId === firstBody.audit.runId).length).toBe(1);
  });
});
