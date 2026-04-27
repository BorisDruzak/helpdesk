import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SchemaParamEditor, type SchemaParamField } from "./schema-param-editor";

describe("SchemaParamEditor", () => {
  it("builds params from controlled fields without raw JSON for primitive schema values", () => {
    const onChange = vi.fn();
    const fields: SchemaParamField[] = [
      {
        name: "preset",
        label: "Preset",
        type: "string",
        options: [
          { value: "network", label: "Network" },
          { value: "system", label: "System" },
        ],
      },
      { name: "tail_lines", label: "Tail lines", type: "integer", default: 200 },
      { name: "include_logs", label: "Include logs", type: "boolean", default: false },
    ];

    render(<SchemaParamEditor fields={fields} onChange={onChange} value={{}} />);

    expect(screen.getByLabelText("Preset")).toBeInTheDocument();
    expect(screen.queryByLabelText("Params JSON")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Preset"), { target: { value: "system" } });
    fireEvent.change(screen.getByLabelText("Tail lines"), { target: { value: "500" } });
    fireEvent.click(screen.getByLabelText("Include logs"));

    expect(onChange).toHaveBeenLastCalledWith({
      preset: "system",
      tail_lines: 500,
      include_logs: true,
    });
  });

  it("keeps object params in a bounded advanced field when no safer shape is available", () => {
    const onChange = vi.fn();
    const fields: SchemaParamField[] = [
      {
        name: "filters",
        label: "Filters",
        type: "object",
        default: { severity: "error" },
      },
    ];

    render(<SchemaParamEditor fields={fields} onChange={onChange} value={{}} />);

    const advancedField = screen.getByLabelText("Filters JSON");
    expect(advancedField).toBeInTheDocument();

    fireEvent.change(advancedField, { target: { value: "{\"severity\":\"warning\"}" } });

    expect(onChange).toHaveBeenLastCalledWith({
      filters: { severity: "warning" },
    });
  });
});
