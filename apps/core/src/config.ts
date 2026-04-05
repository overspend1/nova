import crypto from "node:crypto";
import os from "node:os";
import path from "node:path";

export interface NovaCoreConfig {
  pipePath: string;
  authToken: string;
  profileRoot: string;
  auditFilePath: string;
  memoryRootPath: string;
  allowInstallCommands: boolean;
  authMinTokenLength: number;
}

export function loadConfig(): NovaCoreConfig {
  const profileRoot = process.env.NOVA_PROFILE_ROOT ?? os.homedir();
  const baseDataPath = process.env.NOVA_DATA_PATH ?? path.join(profileRoot, ".nova");

  return {
    pipePath: resolvePipePath(process.env.NOVA_PIPE_PATH),
    authToken: process.env.NOVA_AUTH_TOKEN ?? crypto.randomBytes(24).toString("hex"),
    profileRoot,
    auditFilePath:
      process.env.NOVA_AUDIT_FILE ?? path.join(baseDataPath, "audit", "timeline.jsonl"),
    memoryRootPath:
      process.env.NOVA_MEMORY_ROOT ?? path.join(baseDataPath, "memory"),
    allowInstallCommands: process.env.NOVA_ALLOW_INSTALL_COMMANDS === "true",
    authMinTokenLength: resolveMinTokenLength(process.env.NOVA_AUTH_MIN_TOKEN_LENGTH)
  };
}

function resolvePipePath(input?: string): string {
  if (input && input.startsWith("\\\\.\\")) {
    return input;
  }

  const pipeName = input ?? "nova-core-v1";
  return `\\\\.\\pipe\\${pipeName}`;
}

function resolveMinTokenLength(input?: string): number {
  const parsed = Number.parseInt(input ?? "", 10);
  if (Number.isFinite(parsed) && parsed >= 16) {
    return parsed;
  }
  return 16;
}
