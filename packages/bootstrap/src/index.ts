import path from "node:path";
import type { ActionStep, BootstrapSpec } from "@nova/contracts";

const DEFAULT_PROJECT_NAME = "nova-generated-app";

export interface BootstrapSpecValidationResult {
  valid: boolean;
  errors: string[];
}

export function inferBootstrapSpecFromBrief(
  brief: string,
  targetDirectory: string
): BootstrapSpec {
  const inferredName =
    extractProjectName(brief) ??
    (brief.toLowerCase().includes("api") ? "nova-service" : DEFAULT_PROJECT_NAME);
  const projectName = sanitizeProjectName(inferredName);

  const spec: BootstrapSpec = {
    projectName,
    targetDirectory,
    description: brief,
    packageManager: "pnpm",
    stack: "ts-fullstack-default",
    features: {
      web: true,
      api: true,
      worker: true,
      postgres: true,
      redis: true,
      docker: true,
      githubActions: true
    }
  };

  ensureBootstrapSpecValid(spec);
  return spec;
}

export function validateBootstrapSpec(
  spec: BootstrapSpec
): BootstrapSpecValidationResult {
  const errors: string[] = [];

  if (!/^[a-z0-9][a-z0-9-]*$/i.test(spec.projectName)) {
    errors.push("projectName must be a slug-like value (letters, numbers, hyphens).");
  }

  if (!spec.targetDirectory.trim()) {
    errors.push("targetDirectory is required.");
  }

  if (spec.packageManager !== "pnpm") {
    errors.push("Only pnpm is supported in Nova v1.");
  }

  if (spec.stack === "ts-fullstack-default") {
    if (!spec.features.web || !spec.features.api || !spec.features.worker) {
      errors.push("Default stack requires web, api, and worker features.");
    }
    if (!spec.features.postgres || !spec.features.redis) {
      errors.push("Default stack requires postgres and redis features.");
    }
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

export function planBootstrapActions(spec: BootstrapSpec): ActionStep[] {
  ensureBootstrapSpecValid(spec);
  const targetRoot = path.join(spec.targetDirectory, spec.projectName);
  return [
    {
      id: "bootstrap-create-root",
      title: "Create project root",
      description: `Create scaffold root at ${targetRoot}.`,
      kind: "write",
      risk: "high",
      requiresApproval: true,
      dryRunPreview: `mkdir ${targetRoot}`
    },
    {
      id: "bootstrap-write-files",
      title: "Write project files",
      description:
        "Generate Next.js web app, Fastify API, BullMQ worker, Docker Compose, CI workflow, env templates, and docs.",
      kind: "bootstrap",
      risk: "high",
      requiresApproval: true,
      dryRunPreview: "write production-ready monorepo scaffold"
    },
    {
      id: "bootstrap-install",
      title: "Install dependencies",
      description: "Install workspace dependencies with pnpm.",
      kind: "install",
      risk: "high",
      requiresApproval: true,
      command: "pnpm",
      args: ["install"],
      workingDirectory: targetRoot,
      dryRunPreview: `cd ${targetRoot} && pnpm install`
    }
  ];
}

export function materializeBootstrapFiles(
  spec: BootstrapSpec
): Record<string, string> {
  ensureBootstrapSpecValid(spec);
  const root = spec.projectName;
  return {
    [`${root}/.gitignore`]: scaffoldGitignore(),
    [`${root}/.editorconfig`]: scaffoldEditorConfig(),
    [`${root}/.npmrc`]: scaffoldNpmrc(),
    [`${root}/README.md`]: scaffoldReadme(spec),
    [`${root}/pnpm-workspace.yaml`]: scaffoldPnpmWorkspace(),
    [`${root}/package.json`]: scaffoldRootPackageJson(spec),
    [`${root}/tsconfig.base.json`]: scaffoldTsconfigBase(),
    [`${root}/.env.example`]: scaffoldEnvExample(),
    [`${root}/docker-compose.yml`]: scaffoldDockerCompose(),
    [`${root}/.github/workflows/ci.yml`]: scaffoldCiWorkflow(),
    [`${root}/apps/web/package.json`]: scaffoldWebPackageJson(),
    [`${root}/apps/web/next.config.mjs`]: scaffoldWebNextConfig(),
    [`${root}/apps/web/tsconfig.json`]: scaffoldWebTsconfig(),
    [`${root}/apps/web/app/layout.tsx`]: scaffoldWebLayout(),
    [`${root}/apps/web/app/page.tsx`]: scaffoldWebPage(),
    [`${root}/apps/web/app/globals.css`]: scaffoldWebCss(),
    [`${root}/apps/web/.env.local.example`]: scaffoldWebEnvExample(),
    [`${root}/apps/api/package.json`]: scaffoldApiPackageJson(),
    [`${root}/apps/api/tsconfig.json`]: scaffoldApiTsconfig(),
    [`${root}/apps/api/src/index.ts`]: scaffoldApiEntry(),
    [`${root}/apps/api/src/routes/health.ts`]: scaffoldApiHealthRoute(),
    [`${root}/apps/api/src/routes/jobs.ts`]: scaffoldApiJobsRoute(),
    [`${root}/apps/api/.env.example`]: scaffoldApiEnvExample(),
    [`${root}/apps/worker/package.json`]: scaffoldWorkerPackageJson(),
    [`${root}/apps/worker/tsconfig.json`]: scaffoldWorkerTsconfig(),
    [`${root}/apps/worker/src/index.ts`]: scaffoldWorkerEntry(),
    [`${root}/apps/worker/.env.example`]: scaffoldWorkerEnvExample(),
    [`${root}/packages/shared/package.json`]: scaffoldSharedPackageJson(),
    [`${root}/packages/shared/tsconfig.json`]: scaffoldSharedTsconfig(),
    [`${root}/packages/shared/src/index.ts`]: scaffoldSharedEntry(),
    [`${root}/packages/shared/src/queue.ts`]: scaffoldSharedQueue(),
    [`${root}/docs/architecture.md`]: scaffoldArchitectureDoc(spec),
    [`${root}/docs/runbook.md`]: scaffoldRunbookDoc()
  };
}

function ensureBootstrapSpecValid(spec: BootstrapSpec): void {
  const validation = validateBootstrapSpec(spec);
  if (!validation.valid) {
    throw new Error(`Invalid bootstrap spec: ${validation.errors.join(" ")}`);
  }
}

function extractProjectName(brief: string): string | undefined {
  const quoted = brief.match(/(?:called|named)\s+["']([^"']+)["']/i);
  if (quoted?.[1]) {
    return quoted[1];
  }

  const plain = brief.match(/(?:called|named)\s+([a-zA-Z0-9-_]+)/i);
  return plain?.[1];
}

function sanitizeProjectName(input: string): string {
  const normalized = input
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return normalized || DEFAULT_PROJECT_NAME;
}

function scaffoldGitignore(): string {
  return `node_modules/
dist/
.env
.env.local
.next/
coverage/
pnpm-debug.log
`;
}

function scaffoldEditorConfig(): string {
  return `root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
`;
}

function scaffoldNpmrc(): string {
  return `auto-install-peers=true
strict-peer-dependencies=false
`;
}

function scaffoldReadme(spec: BootstrapSpec): string {
  return `# ${spec.projectName}

Generated by Nova bootstrap.

## Stack
- Web: Next.js (TypeScript)
- API: Fastify
- Worker: BullMQ
- Infra: PostgreSQL + Redis via Docker Compose
- CI: GitHub Actions
- Package manager: pnpm

## Quick Start
\`\`\`bash
pnpm install
pnpm dev:infra
pnpm dev
\`\`\`

## One-command Validation
\`\`\`bash
pnpm check
\`\`\`
`;
}

function scaffoldPnpmWorkspace(): string {
  return `packages:
  - "apps/*"
  - "packages/*"
`;
}

function scaffoldRootPackageJson(spec: BootstrapSpec): string {
  return JSON.stringify(
    {
      name: spec.projectName,
      private: true,
      packageManager: "pnpm@10.8.1",
      scripts: {
        dev: "pnpm --parallel --filter @nova/web --filter @nova/api --filter @nova/worker dev",
        "dev:infra": "docker compose up -d",
        "dev:all": "pnpm dev:infra && pnpm dev",
        build: "pnpm -r --if-present build",
        lint: "pnpm -r --if-present lint",
        test: "pnpm -r --if-present test",
        check: "pnpm lint && pnpm test && pnpm build"
      }
    },
    null,
    2
  );
}

function scaffoldTsconfigBase(): string {
  return `{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true
  }
}
`;
}

function scaffoldEnvExample(): string {
  return `POSTGRES_DB=nova
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
DATABASE_URL=postgres://postgres:postgres@localhost:5432/nova
REDIS_URL=redis://localhost:6379
API_PORT=4000
WEB_PORT=3000
`;
}

function scaffoldDockerCompose(): string {
  return `version: "3.9"
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: nova
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    restart: unless-stopped
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 10
`;
}

function scaffoldCiWorkflow(): string {
  return `name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 10
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: "pnpm"
      - run: pnpm install --frozen-lockfile=false
      - run: pnpm lint
      - run: pnpm test
      - run: pnpm build
`;
}

function scaffoldWebPackageJson(): string {
  return JSON.stringify(
    {
      name: "@nova/web",
      private: true,
      scripts: {
        dev: "next dev -p ${WEB_PORT:-3000}",
        build: "next build",
        start: "next start -p ${WEB_PORT:-3000}",
        lint: "next lint",
        test: "echo \"no web tests yet\""
      },
      dependencies: {
        next: "^15.3.0",
        react: "^19.1.0",
        "react-dom": "^19.1.0"
      },
      devDependencies: {
        typescript: "^5.9.2",
        eslint: "^9.32.0",
        "eslint-config-next": "^15.3.0",
        "@types/react": "^19.1.3",
        "@types/node": "^24.5.2"
      }
    },
    null,
    2
  );
}

function scaffoldWebNextConfig(): string {
  return `/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true
};

export default nextConfig;
`;
}

function scaffoldWebTsconfig(): string {
  return `{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "lib": ["dom", "es2022"],
    "jsx": "preserve",
    "incremental": true
  },
  "include": ["**/*.ts", "**/*.tsx"]
}
`;
}

function scaffoldWebLayout(): string {
  return `import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nova Workspace",
  description: "Generated by Nova"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
`;
}

function scaffoldWebPage(): string {
  return `export default async function Page() {
  return (
    <main className="page">
      <h1>Nova scaffold is ready</h1>
      <p>Web, API, and Worker are wired in one pnpm monorepo.</p>
      <ul>
        <li>Run <code>pnpm dev:infra</code> to boot PostgreSQL and Redis.</li>
        <li>Run <code>pnpm dev</code> to start all services.</li>
      </ul>
    </main>
  );
}
`;
}

function scaffoldWebCss(): string {
  return `:root {
  color-scheme: light;
  font-family: "Segoe UI", Arial, sans-serif;
}

body {
  margin: 0;
  background: #f6f8fb;
  color: #172133;
}

.page {
  max-width: 760px;
  margin: 3rem auto;
  background: #ffffff;
  border-radius: 12px;
  padding: 2rem;
  box-shadow: 0 16px 36px rgba(21, 34, 56, 0.08);
}
`;
}

function scaffoldWebEnvExample(): string {
  return `NEXT_PUBLIC_API_BASE_URL=http://localhost:4000
`;
}

function scaffoldApiPackageJson(): string {
  return JSON.stringify(
    {
      name: "@nova/api",
      private: true,
      scripts: {
        dev: "tsx watch src/index.ts",
        build: "tsc -p tsconfig.json",
        start: "node dist/index.js",
        test: "echo \"no api tests yet\"",
        lint: "tsc -p tsconfig.json --noEmit"
      },
      dependencies: {
        fastify: "^5.6.0",
        bullmq: "^5.58.0",
        ioredis: "^5.7.0",
        "@nova/shared": "workspace:*"
      },
      devDependencies: {
        tsx: "^4.20.5",
        typescript: "^5.9.2",
        "@types/node": "^24.5.2"
      }
    },
    null,
    2
  );
}

function scaffoldApiTsconfig(): string {
  return `{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*.ts"]
}
`;
}

function scaffoldApiEntry(): string {
  return `import Fastify from "fastify";
import { registerHealthRoutes } from "./routes/health.js";
import { registerJobsRoutes } from "./routes/jobs.js";

const app = Fastify({ logger: true });
const port = Number(process.env.API_PORT ?? 4000);

await registerHealthRoutes(app);
await registerJobsRoutes(app);

app.listen({ port, host: "0.0.0.0" }).catch((error) => {
  app.log.error(error);
  process.exit(1);
});
`;
}

function scaffoldApiHealthRoute(): string {
  return `import type { FastifyInstance } from "fastify";

export async function registerHealthRoutes(app: FastifyInstance): Promise<void> {
  app.get("/health", async () => ({
    ok: true,
    service: "api"
  }));
}
`;
}

function scaffoldApiJobsRoute(): string {
  return `import type { FastifyInstance } from "fastify";
import { Queue } from "bullmq";
import { JOB_QUEUE_NAME } from "@nova/shared";

const queue = new Queue(JOB_QUEUE_NAME, {
  connection: {
    host: process.env.REDIS_HOST ?? "127.0.0.1",
    port: Number(process.env.REDIS_PORT ?? 6379)
  }
});

export async function registerJobsRoutes(app: FastifyInstance): Promise<void> {
  app.post("/jobs/warmup", async () => {
    const job = await queue.add("warmup", { createdAt: new Date().toISOString() });
    return { ok: true, id: job.id };
  });
}
`;
}

function scaffoldApiEnvExample(): string {
  return `API_PORT=4000
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
`;
}

function scaffoldWorkerPackageJson(): string {
  return JSON.stringify(
    {
      name: "@nova/worker",
      private: true,
      scripts: {
        dev: "tsx watch src/index.ts",
        build: "tsc -p tsconfig.json",
        start: "node dist/index.js",
        test: "echo \"no worker tests yet\"",
        lint: "tsc -p tsconfig.json --noEmit"
      },
      dependencies: {
        bullmq: "^5.58.0",
        ioredis: "^5.7.0",
        "@nova/shared": "workspace:*"
      },
      devDependencies: {
        tsx: "^4.20.5",
        typescript: "^5.9.2",
        "@types/node": "^24.5.2"
      }
    },
    null,
    2
  );
}

function scaffoldWorkerTsconfig(): string {
  return `{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*.ts"]
}
`;
}

function scaffoldWorkerEntry(): string {
  return `import { Worker } from "bullmq";
import { JOB_QUEUE_NAME } from "@nova/shared";

const worker = new Worker(
  JOB_QUEUE_NAME,
  async (job) => {
    console.log("Processing job", job.id, job.name, job.data);
    return { processedAt: new Date().toISOString() };
  },
  {
    connection: {
      host: process.env.REDIS_HOST ?? "127.0.0.1",
      port: Number(process.env.REDIS_PORT ?? 6379)
    }
  }
);

worker.on("completed", (job) => {
  console.log("Completed", job.id);
});
`;
}

function scaffoldWorkerEnvExample(): string {
  return `REDIS_HOST=127.0.0.1
REDIS_PORT=6379
`;
}

function scaffoldSharedPackageJson(): string {
  return JSON.stringify(
    {
      name: "@nova/shared",
      private: true,
      main: "dist/index.js",
      types: "dist/index.d.ts",
      scripts: {
        build: "tsc -p tsconfig.json",
        lint: "tsc -p tsconfig.json --noEmit",
        test: "echo \"no shared tests yet\""
      },
      devDependencies: {
        typescript: "^5.9.2"
      }
    },
    null,
    2
  );
}

function scaffoldSharedTsconfig(): string {
  return `{
  "extends": "../../tsconfig.base.json",
  "compilerOptions": {
    "outDir": "dist",
    "rootDir": "src"
  },
  "include": ["src/**/*.ts"]
}
`;
}

function scaffoldSharedEntry(): string {
  return `export * from "./queue.js";
`;
}

function scaffoldSharedQueue(): string {
  return `export const JOB_QUEUE_NAME = "nova-jobs";
`;
}

function scaffoldArchitectureDoc(spec: BootstrapSpec): string {
  return `# Architecture

This repository was generated by Nova.

## Project
- Name: ${spec.projectName}
- Stack: ${spec.stack}
- Generated: ${new Date().toISOString()}

## Services
- \`apps/web\`: Next.js frontend
- \`apps/api\`: Fastify API and queue ingress
- \`apps/worker\`: BullMQ worker runtime
- \`packages/shared\`: shared queue contract
`;
}

function scaffoldRunbookDoc(): string {
  return `# Runbook

## Local Development
1. Copy \`.env.example\` values as needed.
2. Run \`pnpm install\`.
3. Run \`pnpm dev:infra\`.
4. Run \`pnpm dev\`.

## Validation
- \`pnpm lint\`
- \`pnpm test\`
- \`pnpm build\`
- \`pnpm check\` to run all three in sequence.
`;
}
