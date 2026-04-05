from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from ..actions import ToolRegistry
from ..intent import parse_intent
from ..llm import LLMService
from ..models import ActionStep, Intent, ModelRouteDecision
from ..planner import create_action_plan, route_model


@dataclass
class PlanResult:
    intent: Intent
    route: ModelRouteDecision
    steps: list[ActionStep]
    source: str
    rawModelOutput: str | None = None


class AgentPlanner:
    def __init__(self, llm: LLMService, tools: ToolRegistry) -> None:
        self.llm = llm
        self.tools = tools

    def plan(
        self,
        *,
        prompt: str,
        channel: str,
        metadata: dict[str, str] | None = None,
        max_steps: int = 8,
    ) -> PlanResult:
        intent = parse_intent(prompt, channel=channel, metadata=metadata or {})
        route = route_model(intent)

        llm_steps, raw = self._plan_with_llm(prompt=prompt, intent=intent, max_steps=max_steps)
        if llm_steps:
            return PlanResult(
                intent=intent,
                route=route,
                steps=llm_steps,
                source="llm",
                rawModelOutput=raw,
            )

        fallback = create_action_plan(intent)
        return PlanResult(
            intent=intent,
            route=route,
            steps=fallback[:max_steps],
            source="heuristic",
            rawModelOutput=raw,
        )

    def replan(
        self,
        *,
        prompt: str,
        intent: Intent,
        previous_steps: list[ActionStep],
        failure_summary: str,
        max_steps: int = 8,
    ) -> list[ActionStep]:
        previous = [
            {
                "id": step.id,
                "title": step.title,
                "toolName": step.toolName,
                "kind": step.kind,
            }
            for step in previous_steps
        ]
        planning_prompt = (
            f"Original prompt: {prompt}\n"
            f"Intent type: {intent.taskType}\n"
            f"Previous steps: {json.dumps(previous)}\n"
            f"Failure summary: {failure_summary}\n"
            "Create a corrected plan that avoids the same failure."
        )
        steps, _raw = self._plan_with_llm(
            prompt=planning_prompt,
            intent=intent,
            max_steps=max_steps,
        )
        return steps or previous_steps[:max_steps]

    def _plan_with_llm(
        self,
        *,
        prompt: str,
        intent: Intent,
        max_steps: int,
    ) -> tuple[list[ActionStep], str | None]:
        declarations = self.tools.declarations()
        planner_instruction = (
            "Return strict JSON with shape: "
            '{"steps":[{"title":"...", "description":"...", "tool":"tool.name", "arguments":{}}]}. '
            "Choose only tool values from the provided tool catalog. "
            f"Limit to max {max_steps} steps."
        )
        tool_text = json.dumps(declarations, indent=2)
        model_input = (
            f"{planner_instruction}\n"
            f"Task intent type: {intent.taskType}\n"
            f"Tool catalog:\n{tool_text}\n"
            f"User task:\n{prompt}"
        )
        result = self.llm.generate(
            prompt=model_input,
            context_hint="planner-json",
            temperature=0.1,
            system_override=(
                "You are Nova planner. Output ONLY JSON and no markdown. "
                "Use available tools and keep plans concise."
            ),
        )
        raw = result.content
        if not result.ok:
            return [], raw

        payload = _parse_json_payload(raw)
        steps_data = payload.get("steps") if isinstance(payload, dict) else None
        if not isinstance(steps_data, list):
            return [], raw

        built: list[ActionStep] = []
        for item in steps_data[:max_steps]:
            if not isinstance(item, dict):
                continue
            tool_name = str(item.get("tool", "")).strip()
            spec = self.tools.get(tool_name)
            if spec is None:
                continue
            arguments = item.get("arguments", {})
            if not isinstance(arguments, dict):
                arguments = {}
            built.append(
                ActionStep(
                    id=f"step_{uuid.uuid4().hex[:8]}",
                    title=str(item.get("title", tool_name)).strip() or tool_name,
                    description=str(item.get("description", spec.description)).strip()
                    or spec.description,
                    kind=spec.kind,
                    risk=spec.risk,
                    requiresApproval=spec.requires_approval,
                    toolName=tool_name,
                    toolArgs={str(key): value for key, value in arguments.items()},
                    dryRunPreview=f"{tool_name}({json.dumps(arguments, ensure_ascii=True)})",
                )
            )
        return built, raw


def _parse_json_payload(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        try:
            payload = json.loads(fenced.group(1))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        candidate = text[brace_start : brace_end + 1]
        try:
            payload = json.loads(candidate)
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}
