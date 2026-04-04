import fs from "node:fs/promises";
import path from "node:path";
import type { ExecutionAudit } from "@nova/contracts";

export class AuditLog {
  constructor(private readonly filePath: string) {}

  async append(audit: ExecutionAudit): Promise<void> {
    await fs.mkdir(path.dirname(this.filePath), { recursive: true });
    const line = `${JSON.stringify(audit)}\n`;
    await fs.appendFile(this.filePath, line, "utf-8");
  }

  async list(limit = 100): Promise<ExecutionAudit[]> {
    try {
      const raw = await fs.readFile(this.filePath, "utf-8");
      const lines = raw
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      return lines
        .slice(-limit)
        .map((line) => JSON.parse(line) as ExecutionAudit)
        .reverse();
    } catch {
      return [];
    }
  }
}

