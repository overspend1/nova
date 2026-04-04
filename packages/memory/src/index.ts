import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import type { MemoryRecord, WorkspaceContext } from "@nova/contracts";

const DEFAULT_EXCLUDES = [
  ".git",
  "node_modules",
  ".next",
  "dist",
  "bin",
  "obj",
  "AppData",
  "Program Files",
  "ProgramData"
];

export class MemoryStore {
  private readonly dataPath: string;
  private readonly recordsFile: string;
  private readonly indexConfigFile: string;

  constructor(basePath = path.join(os.homedir(), ".nova", "memory")) {
    this.dataPath = basePath;
    this.recordsFile = path.join(basePath, "records.json");
    this.indexConfigFile = path.join(basePath, "workspace-context.json");
  }

  async upsert(record: MemoryRecord): Promise<MemoryRecord> {
    const records = await this.readRecords();
    const now = new Date().toISOString();
    const existing = records.find((item) => item.id === record.id);

    if (existing) {
      existing.content = record.content;
      existing.scope = record.scope;
      existing.tags = record.tags;
      existing.updatedAt = now;
      await this.writeRecords(records);
      return existing;
    }

    const created: MemoryRecord = {
      ...record,
      createdAt: record.createdAt || now,
      updatedAt: now
    };
    records.push(created);
    await this.writeRecords(records);
    return created;
  }

  async search(
    query: string,
    scope?: string,
    limit = 10
  ): Promise<MemoryRecord[]> {
    const records = await this.readRecords();
    const filtered = scope
      ? records.filter((record) => record.scope === scope)
      : records;

    const queryTokens = tokenize(query);
    return filtered
      .map((record) => ({
        record,
        score: scoreContent(record.content, queryTokens, record.tags)
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map((entry) => entry.record);
  }

  async saveWorkspaceContext(input: {
    profileRoot: string;
    indexedPaths?: string[];
    optOutPaths?: string[];
  }): Promise<WorkspaceContext> {
    await fs.mkdir(this.dataPath, { recursive: true });
    const context: WorkspaceContext = {
      cwd: process.cwd(),
      profileRoot: input.profileRoot,
      indexedPaths: input.indexedPaths ?? [input.profileRoot],
      optOutPaths: input.optOutPaths ?? [],
      excludeGlobs: DEFAULT_EXCLUDES
    };
    await fs.writeFile(
      this.indexConfigFile,
      JSON.stringify(context, null, 2),
      "utf-8"
    );
    return context;
  }

  async getWorkspaceContext(profileRoot?: string): Promise<WorkspaceContext> {
    await fs.mkdir(this.dataPath, { recursive: true });
    try {
      const raw = await fs.readFile(this.indexConfigFile, "utf-8");
      return JSON.parse(raw) as WorkspaceContext;
    } catch {
      const resolvedRoot = profileRoot ?? os.homedir();
      return this.saveWorkspaceContext({ profileRoot: resolvedRoot });
    }
  }

  private async readRecords(): Promise<MemoryRecord[]> {
    await fs.mkdir(this.dataPath, { recursive: true });
    try {
      const raw = await fs.readFile(this.recordsFile, "utf-8");
      return JSON.parse(raw) as MemoryRecord[];
    } catch {
      return [];
    }
  }

  private async writeRecords(records: MemoryRecord[]): Promise<void> {
    await fs.mkdir(this.dataPath, { recursive: true });
    await fs.writeFile(this.recordsFile, JSON.stringify(records, null, 2), "utf-8");
  }
}

function tokenize(input: string): string[] {
  return input
    .toLowerCase()
    .split(/[^a-z0-9]+/g)
    .filter(Boolean);
}

function scoreContent(content: string, queryTokens: string[], tags: string[]): number {
  const normalized = content.toLowerCase();
  const tagSet = new Set(tags.map((tag) => tag.toLowerCase()));
  let score = 0;
  for (const token of queryTokens) {
    if (normalized.includes(token)) {
      score += 2;
    }
    if (tagSet.has(token)) {
      score += 3;
    }
  }
  return score;
}

