import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ToolResultEventCard } from "./tool-result-event-card";

describe("ToolResultEventCard", () => {
  it("renders regular tool results through ModuleResultRenderer", () => {
    render(
      <ToolResultEventCard
        result={{ status: "ok" }}
        presentationSchema={{
          version: "1.0",
          kind: "tool_result",
          blocks: [{ type: "field_grid", fields: [{ path: "status", label: "Status" }] }],
        }}
      />
    );

    expect(screen.getByText("Status")).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("renders composite recipe results through CompositeRecipeRenderer", () => {
    render(
      <ToolResultEventCard
        result={{
          summary: { title: "Recipe", message: "Done" },
          steps: [{ title: "DNS", status: "success", primitive_id: "dns.resolve", result: { resolved: true } }],
        }}
        presentationSchema={{
          version: "1.0",
          kind: "composite_recipe",
          steps: {
            path: "steps",
            title_path: "title",
            status_path: "status",
            primitive_id_path: "primitive_id",
            result_path: "result",
            default_layout: "timeline",
          },
        }}
      />
    );

    expect(screen.getByText("Recipe")).toBeInTheDocument();
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.getByText("resolved")).toBeInTheDocument();
  });
});
