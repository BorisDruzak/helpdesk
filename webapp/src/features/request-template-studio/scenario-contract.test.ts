import { describe, expect, it } from "vitest";
import type { ScenarioCondition } from "./scenario-contract";

// Standard Pydantic JSON projection for a result source includes nullable field.
const serverResultCondition = {
  op: "eq", source: "current_result", field: null, value: "yes",
} satisfies ScenarioCondition;

describe("scenario wire contract", () => {
  it("accepts the server result-condition projection", () => {
    expect(JSON.parse(JSON.stringify(serverResultCondition))).toEqual({
      op: "eq", source: "current_result", field: null, value: "yes",
    });
  });
});
