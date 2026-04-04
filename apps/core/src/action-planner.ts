import { nanoid } from "nanoid";
import type { ActionStep, Intent } from "@nova/contracts";

export function createActionPlan(intent: Intent): ActionStep[] {
  switch (intent.taskType) {
    case "retrieval":
      return [
        buildStep({
          title: "Read workspace context",
          description: "Inspect indexed memory and repository context to answer the request.",
          kind: "read",
          risk: "low",
          requiresApproval: false
        }),
        buildStep({
          title: "Search memory store",
          description: "Run semantic memory search for relevant notes and prior decisions.",
          kind: "memory",
          risk: "low",
          requiresApproval: false
        })
      ];
    case "planning":
      return [
        buildStep({
          title: "Analyze constraints",
          description: "Identify project constraints and acceptance criteria.",
          kind: "read",
          risk: "low",
          requiresApproval: false
        }),
        buildStep({
          title: "Draft implementation approach",
          description: "Generate implementation roadmap and optional execution sequence.",
          kind: "read",
          risk: "low",
          requiresApproval: false
        })
      ];
    case "coding":
      return [
        buildStep({
          title: "Inspect target code",
          description: "Read project files and identify exact edit scope.",
          kind: "read",
          risk: "low",
          requiresApproval: false
        }),
        buildStep({
          title: "Apply code changes",
          description:
            "Modify files required by the task. Approval required before any write.",
          kind: "write",
          risk: "high",
          requiresApproval: true
        }),
        buildStep({
          title: "Run validation",
          description: "Execute tests/lint checks relevant to modified modules.",
          kind: "system",
          risk: "medium",
          requiresApproval: true
        })
      ];
    case "bootstrap":
      return [
        buildStep({
          title: "Generate scaffold spec",
          description: "Create structured bootstrap spec from user brief.",
          kind: "bootstrap",
          risk: "medium",
          requiresApproval: false
        }),
        buildStep({
          title: "Write scaffold files",
          description: "Create workspace files for web/api/worker starter.",
          kind: "write",
          risk: "high",
          requiresApproval: true
        }),
        buildStep({
          title: "Install dependencies",
          description: "Install generated project dependencies.",
          kind: "install",
          risk: "high",
          requiresApproval: true
        })
      ];
    case "command":
      return [
        buildStep({
          title: "Dry-run shell command",
          description: "Render command preview and explain impact.",
          kind: "system",
          risk: "medium",
          requiresApproval: true
        })
      ];
    case "unknown":
    default:
      return [
        buildStep({
          title: "Clarify request through context",
          description: "Use local context retrieval and ask for safer next action.",
          kind: "read",
          risk: "low",
          requiresApproval: false
        })
      ];
  }
}

function buildStep(
  input: Omit<ActionStep, "id"> & {
    title: string;
    description: string;
  }
): ActionStep {
  return {
    ...input,
    id: `step_${nanoid(8)}`
  };
}

