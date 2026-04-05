from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException

from .actions import ToolRuntime, build_tool_registry
from .agent import AgentExecutor, AgentPlanner, AgentTaskQueue
from .audit_log import AuditLog
from .bootstrap import (
    infer_bootstrap_spec_from_brief,
    materialize_bootstrap_files,
    plan_bootstrap_actions,
)
from .capabilities import list_capabilities
from .config import CoreConfig, load_config
from .execution import execute_plan
from .intent import parse_intent
from .llm import LLMService
from .memory_store import MemoryStore
from .models import (
    ActionsExecuteRequest,
    ActionsPlanRequest,
    AgentTaskApproveRequest,
    AgentTaskCreateRequest,
    AssistantRespondRequest,
    ApprovalDecision,
    ApprovalRequest,
    BootstrapCreateRequest,
    ExecutionAudit,
    Intent,
    IntentParseRequest,
    MemoryContextRequest,
    MemoryRecord,
    MemorySearchRequest,
    MemoryUpsertRequest,
)
from .planner import route_model

logger = logging.getLogger("nova-core")


def create_app(config: CoreConfig | None = None) -> FastAPI:
    cfg = config or load_config()
    app = FastAPI(title="Nova Python Core", version="1.0.0")
    audit_log = AuditLog(cfg.audit_file)
    memory = MemoryStore(cfg.memory_root)
    llm = LLMService(cfg)
    tools = build_tool_registry()
    tool_runtime = ToolRuntime(config=cfg, memory=memory)
    agent_planner = AgentPlanner(llm=llm, tools=tools)
    agent_executor = AgentExecutor(llm=llm, tools=tools, runtime=tool_runtime)
    agent_queue = AgentTaskQueue(
        planner=agent_planner,
        executor=agent_executor,
        audit_log=audit_log,
    )
    memory.get_workspace_context(str(cfg.profile_root))

    def auth_guard(x_nova_token: str | None = Header(default=None)) -> None:
        if x_nova_token != cfg.auth_token:
            raise HTTPException(status_code=401, detail="Unauthorized request.")

    @app.get("/health")
    def health() -> dict[str, object]:
        return {
            "ok": True,
            "baseUrl": cfg.base_url,
            "profileRoot": str(cfg.profile_root),
            "mode": "python-local-first",
            "modelProvider": cfg.model_provider,
            "model": cfg.local_model,
        }

    @app.get("/meta/capabilities", dependencies=[Depends(auth_guard)])
    def meta_capabilities() -> dict[str, object]:
        return {
            "assistant": "Nova",
            "runtime": "python",
            "executionMode": "local-first",
            "capabilities": list_capabilities(),
        }

    @app.get("/meta/model", dependencies=[Depends(auth_guard)])
    def meta_model() -> dict[str, object]:
        return {
            "provider": cfg.model_provider,
            "model": cfg.local_model,
            "endpoint": cfg.ollama_url,
            "enabled": llm.is_enabled(),
        }

    @app.get("/audit/timeline", dependencies=[Depends(auth_guard)])
    def audit_timeline(limit: int = 100) -> list[dict]:
        return [audit.model_dump() for audit in audit_log.list(limit)]

    @app.post("/intent/parse", dependencies=[Depends(auth_guard)])
    def intent_parse(body: IntentParseRequest) -> dict[str, object]:
        intent = parse_intent(body.input, body.channel, body.metadata)
        route = route_model(intent)
        return {"intent": intent.model_dump(), "route": route.model_dump()}

    @app.post("/actions/plan", dependencies=[Depends(auth_guard)])
    def actions_plan(body: ActionsPlanRequest) -> dict[str, object]:
        plan = agent_planner.plan(
            prompt=body.input,
            channel=body.channel,
            metadata=body.metadata,
        )
        intent = plan.intent
        route = plan.route
        steps = plan.steps
        approval_requests = [
            ApprovalRequest(
                actionId=step.id,
                reason=step.description,
                risk=step.risk,
                requestedAt=utc_now(),
            )
            for step in steps
            if step.requiresApproval
        ]

        audit = ExecutionAudit(
            runId=f"run_{uuid.uuid4().hex}",
            intentId=intent.id,
            plannedAt=utc_now(),
            mode="dry-run",
            status="planned",
            approvals=[],
            steps=[{"stepId": step.id, "status": "pending"} for step in steps],
        )
        audit_log.append(audit)

        return {
            "runId": audit.runId,
            "intent": intent.model_dump(),
            "route": route.model_dump(),
            "steps": [step.model_dump() for step in steps],
            "approvalRequests": [request.model_dump() for request in approval_requests],
            "plannerSource": plan.source,
            "audit": audit.model_dump(),
        }

    @app.get("/actions/catalog", dependencies=[Depends(auth_guard)])
    def actions_catalog() -> dict[str, object]:
        return {
            "capabilities": list_capabilities(),
            "toolRegistry": tools.declarations(),
        }

    @app.post("/assistant/respond", dependencies=[Depends(auth_guard)])
    def assistant_respond(body: AssistantRespondRequest) -> dict[str, object]:
        plan = agent_planner.plan(
            prompt=body.input,
            channel=body.channel,
            metadata=body.metadata,
        )
        intent = plan.intent
        route = plan.route
        steps = plan.steps if body.includePlan else []

        llm_result = llm.generate(
            prompt=body.input,
            context_hint=(
                f"task={intent.taskType}; route={route.route}; includePlan={body.includePlan}"
            ),
        )

        return {
            "intent": intent.model_dump(),
            "route": route.model_dump(),
            "steps": [step.model_dump() for step in steps],
            "response": llm_result.content,
            "plannerSource": plan.source,
            "model": {
                "ok": llm_result.ok,
                "provider": llm_result.provider,
                "model": llm_result.model,
                "error": llm_result.error,
            },
        }

    @app.post("/agent/task", dependencies=[Depends(auth_guard)])
    def create_agent_task(body: AgentTaskCreateRequest) -> dict[str, object]:
        task = agent_queue.create_task(body)
        return {"task": task.model_dump()}

    @app.get("/agent/tasks", dependencies=[Depends(auth_guard)])
    def list_agent_tasks(limit: int = 25) -> dict[str, object]:
        tasks = agent_queue.list_tasks(limit=limit)
        return {"tasks": [task.model_dump() for task in tasks]}

    @app.get("/agent/task/{task_id}", dependencies=[Depends(auth_guard)])
    def get_agent_task(task_id: str) -> dict[str, object]:
        task = agent_queue.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"task": task.model_dump()}

    @app.post("/agent/task/{task_id}/cancel", dependencies=[Depends(auth_guard)])
    def cancel_agent_task(task_id: str) -> dict[str, object]:
        task = agent_queue.cancel_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"task": task.model_dump()}

    @app.post("/agent/task/{task_id}/approve", dependencies=[Depends(auth_guard)])
    def approve_agent_task(task_id: str, body: AgentTaskApproveRequest) -> dict[str, object]:
        decisions = [
            ApprovalDecision(
                actionId=item.actionId,
                approved=item.approved,
                approver=item.approver or "user",
                decidedAt=item.decidedAt or utc_now(),
            )
            for item in body.approvals
        ]
        task = agent_queue.approve_task(task_id, decisions, mode=body.mode)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"task": task.model_dump()}

    @app.post("/actions/execute", dependencies=[Depends(auth_guard)])
    def actions_execute(body: ActionsExecuteRequest) -> dict[str, object]:
        intent: Intent
        if body.intent:
            intent = body.intent
        else:
            intent = parse_intent(body.input or "", body.channel)

        steps = body.steps or agent_planner.plan(
            prompt=body.input or intent.rawInput,
            channel=body.channel,
            metadata=intent.metadata,
        ).steps
        approvals = [
            ApprovalDecision(
                actionId=decision.actionId,
                approved=decision.approved,
                approver=decision.approver or "user",
                decidedAt=decision.decidedAt or utc_now(),
            )
            for decision in body.approvals
        ]

        result = agent_executor.execute(
            prompt=body.input or intent.rawInput,
            intent=intent,
            mode=body.mode,
            steps=steps,
            approvals=approvals,
            run_id=f"run_{uuid.uuid4().hex}",
        )
        audit_log.append(result.audit)
        return {
            "intent": intent.model_dump(),
            "steps": [step.model_dump() for step in steps],
            "approvalRequests": [item.model_dump() for item in result.approval_requests],
            "assistantSummary": result.assistant_summary,
            "audit": result.audit.model_dump(),
        }

    @app.post("/bootstrap/create", dependencies=[Depends(auth_guard)])
    def bootstrap_create(body: BootstrapCreateRequest) -> dict[str, object]:
        target = str(Path(body.targetDirectory or str(Path.cwd())).resolve())
        spec = infer_bootstrap_spec_from_brief(body.brief, target)
        steps = plan_bootstrap_actions(spec)
        approvals = [
            ApprovalDecision(
                actionId=step.id,
                approved=step.id in body.approvedActionIds,
                approver=body.approver,
                decidedAt=utc_now(),
            )
            for step in steps
        ]

        audit = execute_plan(
            run_id=f"run_{uuid.uuid4().hex}",
            intent_id=f"intent_bootstrap_{uuid.uuid4().hex[:8]}",
            mode=body.mode,
            steps=steps,
            approvals=approvals,
            allow_install_commands=cfg.allow_install_commands,
        )

        files_written = 0
        project_root = Path(spec.targetDirectory) / spec.projectName
        approved_set = set(body.approvedActionIds)
        write_approved = {
            "bootstrap-create-root",
            "bootstrap-write-files",
        }.issubset(approved_set)
        if body.mode == "execute" and write_approved:
            for rel_path, content in materialize_bootstrap_files(spec).items():
                absolute = Path(spec.targetDirectory) / rel_path
                absolute.parent.mkdir(parents=True, exist_ok=True)
                absolute.write_text(content, encoding="utf-8")
                files_written += 1

        audit_log.append(audit)
        return {
            "projectRoot": str(project_root),
            "filesWritten": files_written,
            "spec": spec.model_dump(),
            "audit": audit.model_dump(),
        }

    @app.post("/memory/upsert", dependencies=[Depends(auth_guard)])
    def memory_upsert(body: MemoryUpsertRequest) -> dict[str, object]:
        now = utc_now()
        record = memory.upsert(
            MemoryRecord(
                id=body.id or f"mem_{uuid.uuid4().hex[:12]}",
                scope=body.scope,
                content=body.content,
                tags=body.tags,
                createdAt=now,
                updatedAt=now,
            )
        )
        return {"record": record.model_dump()}

    @app.post("/memory/search", dependencies=[Depends(auth_guard)])
    def memory_search(body: MemorySearchRequest) -> dict[str, object]:
        if body.indexedPaths is not None or body.optOutPaths is not None:
            memory.save_workspace_context(
                profile_root=str(cfg.profile_root),
                indexed_paths=body.indexedPaths,
                opt_out_paths=body.optOutPaths,
            )

        if body.refreshIndex:
            memory.refresh_workspace_index(
                profile_root=str(cfg.profile_root),
                indexed_paths=body.indexedPaths,
                opt_out_paths=body.optOutPaths,
                max_files=body.maxFiles or 25_000,
            )

        records = memory.search(body.query, body.scope, body.limit)
        workspace_matches = (
            memory.search_workspace_index(body.query, body.workspaceLimit)
            if body.includeWorkspaceHits
            else []
        )
        context = memory.get_workspace_context(str(cfg.profile_root))
        return {
            "records": [record.model_dump() for record in records],
            "workspaceMatches": [hit.model_dump() for hit in workspace_matches],
            "workspaceContext": context.model_dump(),
        }

    @app.post("/memory/context", dependencies=[Depends(auth_guard)])
    def memory_context(body: MemoryContextRequest) -> dict[str, object]:
        context = memory.save_workspace_context(
            profile_root=body.profileRoot or str(cfg.profile_root),
            indexed_paths=body.indexedPaths,
            opt_out_paths=body.optOutPaths,
        )

        index_info: dict[str, object] | None = None
        if body.reindex:
            index = memory.refresh_workspace_index(
                profile_root=context.profileRoot,
                indexed_paths=context.indexedPaths,
                opt_out_paths=context.optOutPaths,
                max_files=body.maxFiles or 25_000,
            )
            index_info = {
                "generatedAt": index.generatedAt,
                "filesIndexed": len(index.files),
            }
        return {"context": context.model_dump(), "index": index_info}

    return app


def run() -> None:
    config = load_config()
    logging.basicConfig(level=logging.INFO)
    print(f"Nova Python core starting on {config.base_url}")
    print(f"NOVA_AUTH_TOKEN={config.auth_token}")
    uvicorn.run(
        "nova_core.app:create_app",
        factory=True,
        host=config.host,
        port=config.port,
        log_level="info",
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    run()
