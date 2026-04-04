# Nova v1 Architecture

## Components

- `apps/desktop/Nova.Desktop`:
  - WinUI shell
  - voice orchestration (wake-word loop + push-to-talk fallback)
  - approval toggles and audit timeline view
- `apps/core`:
  - Fastify API served via Windows named pipe
  - intent parsing, model routing, action planning, execution gate
  - bootstrap orchestration
  - append-only audit log
- `apps/cli`:
  - `nova zed install` to provision editor tasks
  - `nova run ask` and `nova run bootstrap` helpers
- `packages/contracts`:
  - shared interfaces (`Intent`, `ActionStep`, `BootstrapSpec`, etc.)
- `packages/bootstrap`:
  - scaffold inference, plan generation, and file materialization
- `packages/memory`:
  - local memory records and workspace context defaults

## IPC Boundary

- Transport: local named pipes (`\\.\pipe\nova-core-v1`)
- Protocol: HTTP/1.1
- Authentication: `x-nova-token` header

## Safety

- Mutating steps must include approval decisions.
- Missing approval turns step status into `rejected` and run status into `blocked`.
- Every run is persisted to append-only JSONL timeline.

