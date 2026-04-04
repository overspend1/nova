import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { installZedTasks } from "../../apps/cli/src/index.js";

describe("zed integration", () => {
  const tempDirs: string[] = [];

  afterEach(async () => {
    for (const dir of tempDirs) {
      await fs.rm(dir, { recursive: true, force: true });
    }
  });

  it("writes Nova tasks into .zed/tasks.json", async () => {
    const workspace = await fs.mkdtemp(path.join(os.tmpdir(), "nova-zed-test-"));
    tempDirs.push(workspace);

    await installZedTasks(workspace);

    const raw = await fs.readFile(path.join(workspace, ".zed", "tasks.json"), "utf-8");
    const parsed = JSON.parse(raw);
    const labels = parsed.tasks.map((task: { label: string }) => task.label);
    expect(labels).toContain("Ask Nova");
    expect(labels).toContain("Bootstrap Project");
    expect(labels).toContain("Explain Selection");
    expect(labels).toContain("Refactor via Plan");
  });
});

