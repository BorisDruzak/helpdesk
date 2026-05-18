import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PresentationSchemaBuilder } from "./presentation-builder";
import type { ToolPresentationDetail } from "../../features/capabilities/types";

const capability = {
  id: "system.collect",
  title: "System collect",
  provider_id: "system",
  execution_target: "agent_builtin",
  output_schema: {
    type: "object",
    properties: {
      sections: {
        type: "object",
        properties: {
          network: {
            type: "object",
            properties: {
              hostname: { type: "string", title: "Hostname" },
              primary_ip: { type: "string" },
            },
          },
        },
      },
    },
  },
  presentation_schema: {
    version: "1.0",
    kind: "tool_result",
    title: "Module system",
    blocks: [
      {
        type: "field_grid",
        title: "Identity",
        fields: [{ path: "sections.network.hostname", label: "Hostname" }],
      },
    ],
  },
  effective_presentation_schema: {
    version: "1.0",
    kind: "tool_result",
    title: "Module system",
    blocks: [
      {
        type: "field_grid",
        title: "Identity",
        fields: [{ path: "sections.network.hostname", label: "Hostname" }],
      },
    ],
  },
  presentation_schema_source: "module_default",
  has_presentation_override: false,
};

function detail(source: ToolPresentationDetail["source"] = "module_default"): ToolPresentationDetail {
  const hasOverride = source === "server_override";
  const hasDefault = source === "module_default";
  return {
    tool_id: "system.collect",
    tool_version: null,
    module_default_schema: hasDefault ? capability.presentation_schema : {},
    override_schema: hasOverride ? { version: "1.0", kind: "tool_result", blocks: [{ type: "raw_json" }] } : null,
    effective_schema: hasOverride
      ? { version: "1.0", kind: "tool_result", blocks: [{ type: "raw_json" }] }
      : hasDefault
        ? capability.presentation_schema
        : {},
    source,
    updated_at: null,
    updated_by: null,
  };
}

describe("PresentationSchemaBuilder", () => {
  it("renders editor, output schema path picker and live preview", () => {
    render(<PresentationSchemaBuilder capability={capability} detail={detail()} />);

    expect(screen.getByText("module default")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: /Presentation schema JSON/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sections.network.hostname/i })).toBeInTheDocument();
    expect(screen.getByText("Module system")).toBeInTheDocument();
    expect(screen.getAllByText("Hostname").length).toBeGreaterThan(0);
    expect(screen.getAllByText("example").length).toBeGreaterThan(0);
  });

  it("inserts selected output_schema paths into the JSON editor", () => {
    render(<PresentationSchemaBuilder capability={capability} detail={detail()} />);

    const editor = screen.getByRole("textbox", { name: /Presentation schema JSON/i }) as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: '{ "path": "" }', selectionStart: 11, selectionEnd: 11 } });
    fireEvent.click(screen.getByRole("button", { name: /sections.network.primary_ip/i }));

    expect(editor.value).toContain("sections.network.primary_ip");
  });

  it("shows validation errors for invalid JSON without crashing preview", () => {
    render(<PresentationSchemaBuilder capability={capability} detail={detail()} />);

    fireEvent.change(screen.getByRole("textbox", { name: /Presentation schema JSON/i }), { target: { value: "{" } });
    fireEvent.click(screen.getByRole("button", { name: /Validate/i }));

    expect(screen.getByText(/Invalid JSON/i)).toBeInTheDocument();
    expect(screen.getByText("Live preview")).toBeInTheDocument();
  });

  it("saves parsed override JSON and resets override through callbacks", async () => {
    const onSave = vi.fn(async (schema: unknown) => ({
      ...detail("server_override"),
      override_schema: schema,
      effective_schema: schema,
      source: "server_override" as const,
    }));
    const onReset = vi.fn(async () => detail("module_default"));

    render(<PresentationSchemaBuilder capability={capability} detail={detail("server_override")} onSave={onSave} onReset={onReset} />);

    fireEvent.change(screen.getByRole("textbox", { name: /Presentation schema JSON/i }), {
      target: {
        value: JSON.stringify({ version: "1.0", kind: "tool_result", title: "Edited", blocks: [{ type: "raw_json" }] }),
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /Save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ title: "Edited" })));

    fireEvent.click(screen.getByRole("button", { name: /Reset override/i }));
    await waitFor(() => expect(onReset).toHaveBeenCalledTimes(1));
  });

  it("starts from a raw JSON fallback when no schema exists", () => {
    render(
      <PresentationSchemaBuilder
        capability={{ ...capability, presentation_schema: undefined, effective_presentation_schema: undefined, presentation_schema_source: "none" }}
        detail={detail("none")}
      />,
    );

    expect(screen.getByText("none")).toBeInTheDocument();
    const editor = screen.getByRole("textbox", { name: /Presentation schema JSON/i }) as HTMLTextAreaElement;
    expect(editor.value).toContain('"type": "raw_json"');
  });
});
