import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { MemoryStore } from "../../packages/memory/src/index.js";

describe("memory workspace index", () => {
  let tempDir: string;
  let profileRoot: string;
  let store: MemoryStore;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "nova-memory-test-"));
    profileRoot = path.join(tempDir, "profile");
    await fs.mkdir(path.join(profileRoot, "src"), { recursive: true });
    await fs.mkdir(path.join(profileRoot, "node_modules"), { recursive: true });
    await fs.mkdir(path.join(profileRoot, "opt-out"), { recursive: true });

    await fs.writeFile(path.join(profileRoot, "src", "app.ts"), "export const x = 1;");
    await fs.writeFile(path.join(profileRoot, "node_modules", "skip.ts"), "ignore");
    await fs.writeFile(path.join(profileRoot, "opt-out", "secret.ts"), "hidden");
    await fs.writeFile(path.join(profileRoot, "logo.png"), "binary-ish");

    store = new MemoryStore(path.join(tempDir, ".nova-memory"));
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("indexes profile files with excludes and opt-outs", async () => {
    await store.saveWorkspaceContext({
      profileRoot,
      indexedPaths: [profileRoot],
      optOutPaths: [path.join(profileRoot, "opt-out")]
    });

    const index = await store.refreshWorkspaceIndex({ maxFiles: 1000 });
    const indexedPaths = index.files.map((file) => file.relativePath);

    expect(indexedPaths.some((value) => value.endsWith(path.join("src", "app.ts")))).toBe(
      true
    );
    expect(indexedPaths.some((value) => value.includes("node_modules"))).toBe(false);
    expect(indexedPaths.some((value) => value.includes("opt-out"))).toBe(false);
    expect(indexedPaths.some((value) => value.endsWith("logo.png"))).toBe(false);
  });

  it("returns ranked matches from workspace index", async () => {
    await store.saveWorkspaceContext({
      profileRoot,
      indexedPaths: [profileRoot],
      optOutPaths: []
    });
    await store.refreshWorkspaceIndex({ maxFiles: 1000 });

    const matches = await store.searchWorkspaceIndex("app", 5);
    expect(matches.length).toBeGreaterThan(0);
    expect(matches[0].relativePath).toContain("app.ts");
    expect(matches[0].score).toBeGreaterThan(0);
  });
});
