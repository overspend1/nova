import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { buildServer } from "../../apps/core/src/server.js";
import type { NovaCoreConfig } from "../../apps/core/src/config.js";

describe("core routes integration", () => {
  let tempDir: string;
  let config: NovaCoreConfig;
  let app: Awaited<ReturnType<typeof buildServer>>["app"];

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "nova-core-test-"));
    config = {
      pipePath: "\\\\.\\pipe\\nova-test",
      authToken: "test-token",
      profileRoot: tempDir,
      auditFilePath: path.join(tempDir, "audit", "timeline.jsonl"),
      memoryRootPath: path.join(tempDir, "memory"),
      allowInstallCommands: false
    };

    const serverBundle = await buildServer(config);
    app = serverBundle.app;
  });

  afterEach(async () => {
    await app.close();
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("parses intent with auth", async () => {
    const response = await app.inject({
      method: "POST",
      url: "/intent/parse",
      headers: {
        "x-nova-token": "test-token"
      },
      payload: {
        input: "bootstrap a new project"
      }
    });

    expect(response.statusCode).toBe(200);
    const body = response.json();
    expect(body.intent.taskType).toBe("bootstrap");
    expect(body.route.route).toBe("cloud");
  });

  it("writes and reads memory records", async () => {
    const upsertResponse = await app.inject({
      method: "POST",
      url: "/memory/upsert",
      headers: { "x-nova-token": "test-token" },
      payload: {
        scope: "workspace",
        content: "use fastify for local api",
        tags: ["fastify", "api"]
      }
    });
    expect(upsertResponse.statusCode).toBe(200);

    const searchResponse = await app.inject({
      method: "POST",
      url: "/memory/search",
      headers: { "x-nova-token": "test-token" },
      payload: {
        query: "fastify",
        scope: "workspace"
      }
    });
    expect(searchResponse.statusCode).toBe(200);
    expect(searchResponse.json().records.length).toBeGreaterThan(0);
  });
});

