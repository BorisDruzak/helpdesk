import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SchemaObjectBuilder } from "./schema-object-builder";

describe("SchemaObjectBuilder", () => {
  it("builds object schema rows without exposing an editable JSON textarea", () => {
    const onChange = vi.fn();

    const { container } = render(
      <SchemaObjectBuilder
        label="Params schema"
        onChange={onChange}
        value={{
          type: "object",
          properties: {
            target: {
              type: "string",
              description: "Host to probe",
            },
          },
          required: ["target"],
        }}
      />,
    );

    expect(screen.getByRole("textbox", { name: "Field name" })).toHaveValue("target");
    expect(screen.getByRole("combobox", { name: "Field type" })).toHaveValue("string");
    expect(screen.getByRole("checkbox", { name: "Required" })).toBeChecked();
    expect(container.querySelector("textarea[aria-label='Params schema JSON']")).not.toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "Enum values, one per line" }), {
      target: { value: "gateway\npublic_dns" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Default value" }), {
      target: { value: "gateway" },
    });

    expect(onChange).toHaveBeenLastCalledWith({
      type: "object",
      properties: {
        target: {
          type: "string",
          description: "Host to probe",
          default: "gateway",
          enum: ["gateway", "public_dns"],
        },
      },
      required: ["target"],
    });
  });
});
