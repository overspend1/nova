import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["unit/**/*.test.ts", "integration/**/*.test.ts", "e2e/**/*.test.ts"]
  }
});

