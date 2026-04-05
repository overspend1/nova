import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import type { MemoryRecord, WorkspaceContext, WorkspaceIndexHit } from "@nova/contracts";

const DEFAULT_EXCLUDES = [
  ".git",
  "node_modules",
  ".next",
  "dist",
  "bin",
  "obj",
  "AppData",
  "Program Files",
  "ProgramData",
  "Windows",
  "$Recycle.Bin"
];

const DEFAULT_BINARY_EXTENSIONS = new Set([
  ".7z",
  ".dll",
  ".dylib",
  ".exe",
  ".gif",
  ".ico",
  ".jpeg",
  ".jpg",
  ".mp3",
  ".mp4",
  ".pdf",
  ".png",
  ".ttf",
  ".woff",
  ".woff2",
  ".zip"
]);

const DEFAULT_INDEX_LIMIT = 25000;

interface WorkspaceIndexData {
  generatedAt: string;
  profileRoot: string;
  files: WorkspaceIndexHit[];
}

export class MemoryStore {
  private readonly dataPath: string;
  private readonly recordsFile: string;
  private readonly indexConfigFile: string;
  private readonly workspaceIndexFile: string;

  constructor(basePath = path.join(os.homedir(), ".nova", "memory")) {
    this.dataPath = basePath;
    this.recordsFile = path.join(basePath, "records.json");
    this.indexConfigFile = path.join(basePath, "workspace-context.json");
    this.workspaceIndexFile = path.join(basePath, "workspace-index.json");
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
    const profileRoot = path.resolve(input.profileRoot);
    const indexedPaths = dedupeAndNormalizePaths(input.indexedPaths ?? [profileRoot]);
    const optOutPaths = dedupeAndNormalizePaths(input.optOutPaths ?? []);

    const context: WorkspaceContext = {
      cwd: process.cwd(),
      profileRoot,
      indexedPaths,
      optOutPaths,
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
      const resolvedRoot = path.resolve(profileRoot ?? os.homedir());
      return this.saveWorkspaceContext({ profileRoot: resolvedRoot });
    }
  }

  async refreshWorkspaceIndex(input?: {
    profileRoot?: string;
    indexedPaths?: string[];
    optOutPaths?: string[];
    maxFiles?: number;
  }): Promise<WorkspaceIndexData> {
    const context = input?.indexedPaths || input?.optOutPaths
      ? await this.saveWorkspaceContext({
          profileRoot: input.profileRoot ?? os.homedir(),
          indexedPaths: input.indexedPaths,
          optOutPaths: input.optOutPaths
        })
      : await this.getWorkspaceContext(input?.profileRoot);

    const files: WorkspaceIndexHit[] = [];
    const maxFiles = input?.maxFiles ?? DEFAULT_INDEX_LIMIT;
    for (const indexedPath of context.indexedPaths) {
      await this.walkPath({
        currentPath: indexedPath,
        context,
        output: files,
        maxFiles
      });
      if (files.length >= maxFiles) {
        break;
      }
    }

    const data: WorkspaceIndexData = {
      generatedAt: new Date().toISOString(),
      profileRoot: context.profileRoot,
      files
    };
    await fs.writeFile(this.workspaceIndexFile, JSON.stringify(data, null, 2), "utf-8");
    return data;
  }

  async searchWorkspaceIndex(
    query: string,
    limit = 10
  ): Promise<WorkspaceIndexHit[]> {
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      return [];
    }

    const index = await this.readOrCreateWorkspaceIndex();
    const tokens = tokenize(normalizedQuery);

    return index.files
      .map((entry) => ({
        entry,
        score: scoreWorkspaceEntry(entry, tokens)
      }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map((item) => ({
        ...item.entry,
        score: item.score
      }));
  }

  private async readOrCreateWorkspaceIndex(): Promise<WorkspaceIndexData> {
    await fs.mkdir(this.dataPath, { recursive: true });
    try {
      const raw = await fs.readFile(this.workspaceIndexFile, "utf-8");
      return JSON.parse(raw) as WorkspaceIndexData;
    } catch {
      return this.refreshWorkspaceIndex();
    }
  }

  private async walkPath(input: {
    currentPath: string;
    context: WorkspaceContext;
    output: WorkspaceIndexHit[];
    maxFiles: number;
  }): Promise<void> {
    if (input.output.length >= input.maxFiles) {
      return;
    }

    const resolved = path.resolve(input.currentPath);
    if (shouldSkipPath(resolved, input.context)) {
      return;
    }

    try {
      const entries = await fs.readdir(resolved, {
        withFileTypes: true,
        encoding: "utf8"
      });

      for (const entry of entries) {
        if (input.output.length >= input.maxFiles) {
          return;
        }

        const fullPath = path.join(resolved, entry.name);
        if (entry.isDirectory()) {
          if (isExcludedDirectory(entry.name, input.context.excludeGlobs)) {
            continue;
          }
          await this.walkPath({
            ...input,
            currentPath: fullPath
          });
          continue;
        }

        if (!entry.isFile()) {
          continue;
        }

        if (DEFAULT_BINARY_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) {
          continue;
        }

        let stats: Awaited<ReturnType<typeof fs.stat>>;
        try {
          stats = await fs.stat(fullPath);
        } catch {
          continue;
        }

        const relative = safeRelativePath(input.context.profileRoot, fullPath);
        input.output.push({
          path: fullPath,
          relativePath: relative,
          modifiedAt: stats.mtime.toISOString(),
          size: stats.size,
          score: 0
        });
      }
    } catch {
      return;
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

function dedupeAndNormalizePaths(paths: string[]): string[] {
  const unique = new Set<string>();
  for (const entry of paths) {
    const normalized = path.resolve(entry);
    unique.add(normalized);
  }
  return [...unique];
}

function shouldSkipPath(targetPath: string, context: WorkspaceContext): boolean {
  if (isExcludedDirectory(path.basename(targetPath), context.excludeGlobs)) {
    return true;
  }

  for (const optOut of context.optOutPaths) {
    if (isPathInside(optOut, targetPath)) {
      return true;
    }
  }

  return false;
}

function isExcludedDirectory(name: string, excludes: string[]): boolean {
  const normalized = name.toLowerCase();
  return excludes.some((exclude) => normalized === exclude.toLowerCase());
}

function isPathInside(parent: string, candidate: string): boolean {
  const parentResolved = path.resolve(parent);
  const candidateResolved = path.resolve(candidate);
  return (
    candidateResolved === parentResolved ||
    candidateResolved.startsWith(`${parentResolved}${path.sep}`)
  );
}

function safeRelativePath(base: string, absolute: string): string {
  const relative = path.relative(base, absolute);
  if (relative.startsWith("..")) {
    return absolute;
  }
  return relative;
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

function scoreWorkspaceEntry(entry: WorkspaceIndexHit, tokens: string[]): number {
  const normalizedPath = entry.relativePath.toLowerCase();
  const baseName = path.basename(entry.relativePath).toLowerCase();
  let score = 0;

  for (const token of tokens) {
    if (baseName.includes(token)) {
      score += 6;
    } else if (normalizedPath.includes(token)) {
      score += 3;
    }
  }

  return score;
}
