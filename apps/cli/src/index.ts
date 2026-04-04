#!/usr/bin/env node
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

if (isDirectExecution()) {
  await run(process.argv.slice(2));
}

async function run(argv: string[]): Promise<void> {
  const [command, subcommand, ...rest] = argv;

  if (command === "zed" && subcommand === "install") {
    const workspaceRoot = rest[0] ? path.resolve(rest[0]) : process.cwd();
    await installZedTasks(workspaceRoot);
    console.log(`Nova tasks installed at ${path.join(workspaceRoot, ".zed", "tasks.json")}`);
    return;
  }

  if (command === "run" && subcommand === "ask") {
    const prompt = rest.join(" ").trim();
    if (!prompt) {
      throw new Error("Usage: nova run ask <prompt>");
    }
    const data = await callCore("/actions/plan", { input: prompt });
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  if (command === "run" && subcommand === "bootstrap") {
    const brief = rest.join(" ").trim();
    if (!brief) {
      throw new Error("Usage: nova run bootstrap <brief>");
    }
    const data = await callCore("/bootstrap/create", {
      brief,
      mode: "dry-run"
    });
    console.log(JSON.stringify(data, null, 2));
    return;
  }

  printHelp();
}

export async function installZedTasks(workspaceRoot: string): Promise<void> {
  const zedDir = path.join(workspaceRoot, ".zed");
  await fs.mkdir(zedDir, { recursive: true });
  const tasksPath = path.join(zedDir, "tasks.json");

  const taskConfig = {
    "$schema": "https://zed.dev/schema/tasks/v0.2.0.json",
    tasks: [
      {
        label: "Ask Nova",
        command: "nova",
        args: ["run", "ask", "${ZED_SELECTED_TEXT:-Summarize this file}"],
        use_new_terminal: false,
        reveal: "always"
      },
      {
        label: "Bootstrap Project",
        command: "nova",
        args: ["run", "bootstrap", "Create a production-ready fullstack starter"],
        use_new_terminal: true,
        reveal: "always"
      },
      {
        label: "Explain Selection",
        command: "nova",
        args: ["run", "ask", "Explain this code and suggest improvements: ${ZED_SELECTED_TEXT}"],
        use_new_terminal: false,
        reveal: "always"
      },
      {
        label: "Refactor via Plan",
        command: "nova",
        args: [
          "run",
          "ask",
          "Create a safe refactor plan with risk labels for: ${ZED_SELECTED_TEXT}"
        ],
        use_new_terminal: false,
        reveal: "always"
      }
    ]
  };

  await fs.writeFile(tasksPath, JSON.stringify(taskConfig, null, 2), "utf-8");
}

async function callCore(endpoint: string, body: Record<string, unknown>): Promise<unknown> {
  const pipePath = process.env.NOVA_PIPE_PATH ?? "\\\\.\\pipe\\nova-core-v1";
  const token = process.env.NOVA_AUTH_TOKEN;
  if (!token) {
    throw new Error("NOVA_AUTH_TOKEN is required.");
  }

  const payload = JSON.stringify(body);

  return new Promise((resolve, reject) => {
    const request = http.request(
      {
        method: "POST",
        socketPath: pipePath,
        path: endpoint,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(payload),
          "x-nova-token": token
        }
      },
      (response) => {
        let raw = "";
        response.setEncoding("utf-8");
        response.on("data", (chunk) => {
          raw += chunk;
        });
        response.on("end", () => {
          if (response.statusCode && response.statusCode >= 400) {
            reject(
              new Error(
                `Core request failed (${response.statusCode}): ${raw || response.statusMessage}`
              )
            );
            return;
          }
          resolve(raw ? JSON.parse(raw) : {});
        });
      }
    );

    request.on("error", reject);
    request.write(payload);
    request.end();
  });
}

function printHelp(): void {
  const profile = os.homedir();
  console.log(`Nova CLI

Usage:
  nova zed install [workspace]
  nova run ask <prompt>
  nova run bootstrap <brief>

Environment:
  NOVA_AUTH_TOKEN=<token>  Required for core requests
  NOVA_PIPE_PATH=<pipe>    Optional (default: \\\\.\\pipe\\nova-core-v1)

Default profile root:
  ${profile}
`);
}

function isDirectExecution(): boolean {
  const entry = process.argv[1];
  if (!entry) {
    return false;
  }
  return import.meta.url === pathToFileURL(entry).href;
}
