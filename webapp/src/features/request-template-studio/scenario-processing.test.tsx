import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useState } from "react";
import { ScenarioProcessing } from "./scenario-processing";
import type { ScenarioDraftDefinition } from "./scenario-contract";

afterEach(() => vi.unstubAllGlobals());
it("selects only published registry policies and keeps references local to the draft", async () => {
  const request = vi.fn(async () => new Response(JSON.stringify({ status: "success", data: { policies: { routing: [
    { code: "printer_route", title: "Поддержка печати", version: "1", is_active: true, published_at: "2026-10-11" },
    { code: "unpublished", title: "Черновая политика", version: "1", is_active: true, published_at: null },
  ] } } }), { headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", request);
  function Harness() {
    const [definition, setDefinition] = useState<ScenarioDraftDefinition>({ scenario_key: "printer", title: "Печать", service_code: "it", offering_full_code: "it.printer", process_binding: { request_template_key: "printer" }, blocks: [] });
    return <><ScenarioProcessing definition={definition} disabled={false} onChange={setDefinition} /><output>{definition.process_binding.policy_refs?.routing || "inherit"}</output></>;
  }
  render(<Harness />);
  await screen.findByRole("option", { name: "Поддержка печати" });
  expect(screen.queryByRole("option", { name: "Черновая политика" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Маршрут и очередь"), { target: { value: "printer_route" } });
  expect(screen.getByText("printer_route", { selector: "output" })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Маршрут и очередь"), { target: { value: "" } });
  expect(screen.getByText("inherit", { selector: "output" })).toBeInTheDocument();
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1));
});
