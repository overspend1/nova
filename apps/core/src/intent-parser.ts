import { nanoid } from "nanoid";
import type { Intent, IntentChannel, TaskType } from "@nova/contracts";

const TASK_KEYWORDS: Record<TaskType, string[]> = {
  retrieval: ["find", "search", "where", "explain", "read"],
  planning: ["plan", "design", "architecture", "roadmap"],
  coding: ["fix", "refactor", "implement", "build", "code"],
  bootstrap: ["bootstrap", "scaffold", "new project", "starter", "generate project"],
  command: ["run", "execute", "open", "install", "deploy"],
  unknown: []
};

export function parseIntent(input: {
  text: string;
  channel?: IntentChannel;
  metadata?: Record<string, string>;
}): Intent {
  const normalizedInput = input.text.trim().toLowerCase();
  const taskType = inferTaskType(normalizedInput);

  return {
    id: nanoid(),
    rawInput: input.text,
    normalizedInput,
    channel: input.channel ?? "text",
    taskType,
    confidence: taskType === "unknown" ? 0.45 : 0.85,
    metadata: input.metadata ?? {}
  };
}

function inferTaskType(text: string): TaskType {
  for (const [taskType, words] of Object.entries(TASK_KEYWORDS)) {
    if (words.some((word) => text.includes(word))) {
      return taskType as TaskType;
    }
  }
  return "unknown";
}

