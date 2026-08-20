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

  it("edits object params through bounded nested fields instead of JSON", () => {
    const onChange = vi.fn();
    const fields = [
      {
        name: "filters",
        label: "Filters",
        type: "object",
        properties: [
          {
            name: "severity",
            label: "Severity",
            type: "string",
            default: "error",
            options: [
              { value: "error", label: "Error" },
              { value: "warning", label: "Warning" },
            ],
          },
          {
            name: "include_archived",
            label: "Include archived",
            type: "boolean",
            default: false,
          },
        ],
      },
    ] as unknown as SchemaParamField[];

    render(<SchemaParamEditor fields={fields} onChange={onChange} value={{}} />);

    expect(screen.queryByLabelText("Filters JSON")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Severity")).toBeInTheDocument();
    expect(screen.getByLabelText("Include archived")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Severity"), { target: { value: "warning" } });
    fireEvent.click(screen.getByLabelText("Include archived"));

    expect(onChange).toHaveBeenLastCalledWith({
      filters: { severity: "warning", include_archived: true },
    });
  });

  it("edits array params as explicit rows instead of JSON", () => {
    const onChange = vi.fn();
    const fields = [
      {
        name: "hosts",
        label: "Hosts",
        type: "array",
        default: ["localhost"],
        items: {
          type: "string",
          label: "Host",
        },
      },
    ] as unknown as SchemaParamField[];

    render(<SchemaParamEditor fields={fields} onChange={onChange} value={{}} />);

    expect(screen.queryByLabelText("Hosts JSON")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Host 1")).toHaveValue("localhost");

    fireEvent.change(screen.getByLabelText("Host 1"), { target: { value: "example.test" } });
    fireEvent.click(screen.getByRole("button", { name: "Добавить Host" }));
    fireEvent.change(screen.getByLabelText("Host 2"), { target: { value: "gateway.local" } });

    expect(onChange).toHaveBeenLastCalledWith({
      hosts: ["example.test", "gateway.local"],
    });
  });
});
