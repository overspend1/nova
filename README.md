# Nova v1

Nova is a native Windows "second mind" assistant for developer workflows.

## What Is Implemented

- Native desktop shell with WinUI (`apps/desktop/Nova.Desktop`)
- Local TypeScript core service over authenticated named pipes (`apps/core`)
- Shared typed contracts (`packages/contracts`)
- Opinionated full-stack bootstrap generator (`packages/bootstrap`)
- Local memory store with workspace context (`packages/memory`)
- CLI with Zed integration (`apps/cli`)
- Unit/integration/e2e tests (`tests`)

## Core API (Named Pipe HTTP)

- `POST /intent/parse`
- `POST /actions/plan`
- `POST /actions/execute`
- `POST /bootstrap/create`
- `POST /memory/search`
- `POST /memory/upsert`
- `GET /audit/timeline`

## Security Gate

Any mutating/system operation is approval-gated:

- file writes / bootstrap
- package install
- git/system/network command classes

Core execution blocks these actions if the approval map is missing or rejected.

## Quick Start

1. Install dependencies:
   - `pnpm install`
2. Start core:
   - `pnpm --filter @nova/core dev`
3. In another shell, set token from core logs:
   - PowerShell: `$env:NOVA_AUTH_TOKEN="<token>"`
4. Install Zed tasks in any workspace:
   - `pnpm --filter @nova/cli dev -- zed install C:\path\to\workspace`
5. Optional desktop app:
   - Open `apps/desktop/Nova.Desktop/Nova.Desktop.csproj` in Visual Studio 2022 and run.

## Notes

- Core defaults to indexing user profile context and stores runtime data under `%USERPROFILE%\.nova`.
- Install command execution is disabled unless `NOVA_ALLOW_INSTALL_COMMANDS=true`.
- Desktop wake-word loop currently uses a placeholder polling loop with push-to-talk fallback fully wired.
