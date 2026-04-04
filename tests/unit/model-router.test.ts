import { describe, expect, it } from "vitest";
import { routeModel } from "../../apps/core/src/model-router.js";
import type { Intent } from "@nova/contracts";

function buildIntent(taskType: Intent["taskType"], input = "hello"): Intent {
  return {
    id: "intent_1",
    rawInput: input,
    normalizedInput: input,
    channel: "text",
    taskType,
    confidence: 0.9,
    metadata: {}
  };
}

describe("model router", () => {
  it("routes retrieval to local", () => {
    const decision = routeModel(buildIntent("retrieval", "search files in workspace"));
    expect(decision.route).toBe("local");
  });

  it("routes long coding intents to cloud", () => {
    const longPrompt = "implement ".repeat(80);
    const decision = routeModel(buildIntent("coding", longPrompt));
    expect(decision.route).toBe("cloud");
  });
});

