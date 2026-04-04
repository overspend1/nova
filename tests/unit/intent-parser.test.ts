import { describe, expect, it } from "vitest";
import { parseIntent } from "../../apps/core/src/intent-parser.js";

describe("intent parser", () => {
  it("infers bootstrap intent from natural language", () => {
    const intent = parseIntent({
      text: "Please bootstrap a new project called Alpha",
      channel: "voice"
    });
    expect(intent.taskType).toBe("bootstrap");
    expect(intent.channel).toBe("voice");
    expect(intent.confidence).toBeGreaterThan(0.8);
  });

  it("falls back to unknown for ambiguous input", () => {
    const intent = parseIntent({
      text: "Hmm maybe this",
      channel: "text"
    });
    expect(intent.taskType).toBe("unknown");
  });
});

