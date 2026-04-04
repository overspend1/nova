import type { Intent, ModelRouteDecision } from "@nova/contracts";

export function routeModel(intent: Intent): ModelRouteDecision {
  const complexity = inferComplexity(intent);

  if (intent.taskType === "retrieval" || intent.taskType === "command") {
    return {
      taskType: intent.taskType,
      complexity,
      route: "local",
      reason: "Low-latency local route for retrieval/command tasks."
    };
  }

  if (intent.taskType === "coding" || intent.taskType === "planning") {
    return {
      taskType: intent.taskType,
      complexity,
      route: complexity === "high" ? "cloud" : "local",
      reason: "Coding/planning route selected by complexity policy."
    };
  }

  if (intent.taskType === "bootstrap") {
    return {
      taskType: intent.taskType,
      complexity,
      route: "cloud",
      reason: "Bootstrap tasks use cloud route for richer reasoning."
    };
  }

  return {
    taskType: intent.taskType,
    complexity,
    route: "local",
    reason: "Fallback local route for unknown task."
  };
}

function inferComplexity(intent: Intent): "low" | "medium" | "high" {
  const length = intent.normalizedInput.length;
  if (length < 80) {
    return "low";
  }
  if (length < 280) {
    return "medium";
  }
  return "high";
}

