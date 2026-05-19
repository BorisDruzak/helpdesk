import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  CompositeRecipeRenderer,
  ModuleResultRenderer,
  getPathValue,
  normalizePresentationSchema,
  renderTemplate,
} from "./module-result-renderer";

describe("module result presentation helpers", () => {
  it("reads safe dotted paths and renders simple templates", () => {
    const result = { sections: { network: { hostname: "pc-1" }, platform: { system: "Windows" } } };

    expect(getPathValue(result, "sections.network.hostname")).toBe("pc-1");
    expect(getPathValue(result, "sections.network.__proto__.polluted")).toBeUndefined();
    expect(renderTemplate("{{sections.platform.system}} / {{sections.network.hostname}}", result)).toBe("Windows / pc-1");
  });

  it("treats invalid schemas as missing", () => {
    expect(normalizePresentationSchema("bad")).toBeNull();
    expect(normalizePresentationSchema({ version: "1.0", blocks: "bad" })).toBeNull();
  });
});

describe("ModuleResultRenderer", () => {
  it("renders field grids, metrics, tables, checklist, artifacts and raw json blocks", () => {
    render(
      <ModuleResultRenderer
        result={{
          hostname: "pc-1",
          cpu: 42,
          interfaces: [{ name: "eth0", ipv4: ["10.0.0.5"] }],
          checks: [{ title: "DNS", status: "ok" }],
          artifacts: [{ name: "logs.zip", kind: "logs_zip" }],
        }}
        presentationSchema={{
          version: "1.0",
          kind: "tool_result",
          title: "System",
          summary: { title_path: "hostname", subtitle_template: "CPU {{cpu}}" },
          blocks: [
            { type: "field_grid", title: "Identity", fields: [{ path: "hostname", label: "Host" }] },
            { type: "metric_cards", title: "Metrics", metrics: [{ path: "cpu", label: "CPU", unit: "%" }] },
            {
              type: "table",
              title: "Interfaces",
              rows_path: "interfaces",
              columns: [
                { path: "name", label: "Name" },
                { path: "ipv4", label: "IPv4" },
              ],
            },
            { type: "checklist", title: "Checks", items_path: "checks", label_path: "title", status_path: "status" },
            { type: "artifact_list", title: "Artifacts", items_path: "artifacts", name_path: "name", kind_path: "kind" },
            { type: "raw_json", collapsed: true },
          ],
        }}
      />,
    );

    expect(screen.getByText("System")).toBeInTheDocument();
    expect(screen.getAllByText("pc-1").length).toBeGreaterThan(0);
    expect(screen.getByText("42%")).toBeInTheDocument();
    expect(screen.getByText("eth0")).toBeInTheDocument();
    expect(screen.getByText("10.0.0.5")).toBeInTheDocument();
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.getByText("logs.zip")).toBeInTheDocument();
    expect(screen.getByText("Raw JSON")).toBeInTheDocument();
  });

  it("falls back without crashing for missing paths and unsupported blocks", () => {
    render(
      <ModuleResultRenderer
        result={{ ok: true, message: "<script>alert(1)</script>" }}
        presentationSchema={{
          version: "1.0",
          kind: "tool_result",
          blocks: [
            { type: "unknown_block", id: "bad" },
            { type: "field_grid", fields: [{ path: "missing.value", label: "Missing", empty_text: "empty" }] },
          ],
          fallback: { show_raw_json: true },
        }}
      />,
    );

    expect(screen.getByText("empty")).toBeInTheDocument();
    expect(screen.getByText("Raw JSON")).toBeInTheDocument();
    expect(screen.getByText(/<script>alert/)).toBeInTheDocument();
  });

  it("infers a readable fallback when schema is absent", () => {
    render(<ModuleResultRenderer result={{ status: "ok", rows: [{ name: "first", value: 1 }] }} />);

    expect(screen.getByText("status")).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
    expect(screen.getByText("rows")).toBeInTheDocument();
    expect(screen.getByText("first")).toBeInTheDocument();
  });
});

describe("CompositeRecipeRenderer", () => {
  it("renders recipe steps and delegates step results to primitive schemas", () => {
    render(
      <CompositeRecipeRenderer
        result={{
          status: "success",
          summary: { title: "Network recipe", message: "All checks passed" },
          steps: [
            {
              title: "DNS",
              status: "success",
              primitive_id: "dns.resolve",
              result: { hostname: "example.com", resolved: true, addresses: ["93.184.216.34"] },
            },
          ],
        }}
        presentationSchema={{
          version: "1.0",
          kind: "composite_recipe",
          title: "Recipe",
          summary: { title_path: "summary.title", message_path: "summary.message", status_path: "status" },
          steps: {
            path: "steps",
            title_path: "title",
            status_path: "status",
            primitive_id_path: "primitive_id",
            result_path: "result",
            default_layout: "timeline",
          },
        }}
        primitiveSchemas={{
          "dns.resolve": {
            version: "1.0",
            kind: "tool_result",
            blocks: [{ type: "field_grid", fields: [{ path: "addresses", label: "Addresses" }] }],
          },
        }}
      />,
    );

    expect(screen.getByText("Network recipe")).toBeInTheDocument();
    expect(screen.getByText("DNS")).toBeInTheDocument();
    expect(screen.getByText("93.184.216.34")).toBeInTheDocument();
  });
});
