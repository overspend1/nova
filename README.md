# Nova (Python-First)

Nova is now structured as a Python-native developer assistant stack:

- Core API: `FastAPI` (`python/nova_core`)
- Desktop app: `PySide6` (`python/nova_desktop`)
- Launch scripts: `python/start_core.py`, `python/start_desktop.py`, `python/start_nova.py`

The legacy TypeScript/.NET implementation is still in the repo, but the Python stack is the primary path.

## Features in Python Stack

- `POST /intent/parse`
- `POST /actions/plan`
- `POST /actions/execute`
- `GET /actions/catalog`
- `POST /assistant/respond`
- `POST /agent/task`
- `GET /agent/tasks`
- `GET /agent/task/{task_id}`
- `POST /agent/task/{task_id}/approve`
- `POST /agent/task/{task_id}/cancel`
- `POST /bootstrap/create`
- `POST /memory/search`
- `POST /memory/upsert`
- `POST /memory/context`
- `GET /audit/timeline`
- `GET /meta/capabilities`
- `GET /meta/model`

Safety behavior:

- Mutating/system actions require explicit approval.
- Commands are allowlisted by action type.
- Audit timeline is append-only JSONL.
- Capability catalog is explicit and queryable (tool-style interface).
- Autonomous tasks can replan once after failure and pause on blocked approvals.

Mark-style architecture now included:

- Tool registry (`python/nova_core/actions`) with explicit risk + approval metadata.
- Agent planner/executor/task queue (`python/nova_core/agent`) with status lifecycle.
- Desktop "Command Center" UI with queue controls (queue/view/approve/cancel).

AI model behavior:

- Default provider: `ollama`
- Default model: `qwen3:4b`
- Endpoint: `NOVA_OLLAMA_URL` (default `http://127.0.0.1:11434/api/chat`)

Install local model:

1. Install Ollama: [ollama.com/download](https://ollama.com/download)
2. Pull model:
   - `ollama pull qwen3:4b`
3. Start Ollama (if not auto-started) and run Nova.

## Quick Start (Windows)

1. Install Python deps:
   - `python -m pip install -r python/requirements.txt`
2. Start both core + desktop together:
   - `python python/start_nova.py`
   - `start_nova.py` auto-selects a free local port if `8765` is already in use and keeps core+desktop auth tokens aligned.

Manual start:

1. Start core:
   - `set NOVA_AUTH_TOKEN=your-token`
   - `python python/start_core.py`
2. Start desktop:
   - `set NOVA_AUTH_TOKEN=your-token`
   - `python python/start_desktop.py`

PowerShell equivalent:

- `$env:NOVA_AUTH_TOKEN="your-token"; python python/start_core.py`
- `$env:NOVA_AUTH_TOKEN="your-token"; python python/start_desktop.py`

## Runtime Defaults

- Host: `127.0.0.1`
- Port: `8765`
- Data path: `%USERPROFILE%\.nova-py`
- Install commands disabled unless `NOVA_ALLOW_INSTALL_COMMANDS=true`
- Override model with `NOVA_LOCAL_MODEL=<model-name>`
