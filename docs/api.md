# Nova Core API

All endpoints are served over named-pipe HTTP and require:

- Header: `x-nova-token: <token>`

## `POST /intent/parse`

```json
{
  "input": "bootstrap a project called orbit",
  "channel": "voice"
}
```

## `POST /actions/plan`

```json
{
  "input": "refactor auth module safely",
  "channel": "text"
}
```

Returns parsed intent, model route, and risk-labelled action steps.

## `POST /actions/execute`

```json
{
  "mode": "execute",
  "intent": { "...": "intent object" },
  "steps": [{ "...": "action step" }],
  "approvals": [
    {
      "actionId": "step_123",
      "approved": true,
      "approver": "wiktor"
    }
  ]
}
```

## `POST /bootstrap/create`

```json
{
  "brief": "Create a project called rocket",
  "targetDirectory": "C:/dev",
  "mode": "dry-run"
}
```

Set `mode` to `execute` and pass `approvedActionIds` to materialize files.

## `POST /memory/upsert`

```json
{
  "scope": "workspace",
  "content": "Use fastify for API services.",
  "tags": ["api", "fastify"]
}
```

## `POST /memory/search`

```json
{
  "query": "fastify",
  "scope": "workspace",
  "limit": 5
}
```

## `GET /audit/timeline?limit=20`

Returns append-only execution history.

