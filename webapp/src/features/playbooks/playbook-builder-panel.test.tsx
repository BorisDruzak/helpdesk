import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlaybookBuilderPanel } from "./playbook-builder-panel";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderPanel() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <PlaybookBuilderPanel />
    </QueryClientProvider>,
  );
}

function dataTransferStub(values: Record<string, string>) {
  return {
    effectAllowed: "",
    setData: vi.fn((key: string, value: string) => {
      values[key] = value;
    }),
    getData: vi.fn((key: string) => values[key] ?? ""),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PlaybookBuilderPanel", () => {
  it("builds a diagnostic playbook on a draggable low-code canvas", async () => {
    const saveCalls: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? "GET";

        if (url === "/api/web/admin/playbooks/catalog") {
          return jsonResponse({
            status: "success",
            data: {
              capabilities: {
                catalog_endpoint: "/api/web/admin/playbooks/catalog",
                save_endpoint: "/api/web/admin/playbooks/save",
                block_types: [
                  { value: "diagnostic", label: "Диагностика" },
                  { value: "decision", label: "Условие" },
                  { value: "report", label: "Пакет фактов" },
                ],
                module_kind_options: [
                  { value: "diagnostic", label: "Диагностика" },
                  { value: "remediation", label: "Исправление" },
                ],
              },
              block_catalog: [
                {
                  id: "system.collect",
                  label: "Системный снимок",
                  tool: "system.collect",
                  block_type: "diagnostic",
                  module_kind: "diagnostic",
                  module_name: "system",
                  description: "CPU, память, сеть и платформа",
                  default_params: { preset: "network" },
                  changes_device: false,
                  requires_confirmation: false,
                  output_contract: {
                    status_path: "result.status",
                    status_values: ["ok", "error"],
                    success_values: ["ok"],
                    error_values: ["error"],
                    summary_path: "result.output.summary",
                  },
                  condition_hints: {
                    status_path: "result.status",
                    status_values: ["ok", "error"],
                    error_codes: [],
                    condition_templates: [
                      { label: "status == ok", expression: "{step}.output.result.status == 'ok'" },
                      { label: "status == error", expression: "{step}.output.result.status == 'error'" },
                    ],
                  },
                },
                {
                  id: "diag.logs.collect",
                  label: "Сбор логов",
                  tool: "diag.logs.collect",
                  block_type: "diagnostic",
                  module_kind: "diagnostic",
                  module_name: "diag_logs",
                  description: "Архив логов",
                  default_params: { preset: "system", tail_lines: 500 },
                  changes_device: false,
                  requires_confirmation: true,
                  output_contract: {
                    status_path: "result.status",
                    status_values: ["ok", "error"],
                    success_values: ["ok"],
                    error_values: ["error"],
                    summary_path: "result.output.summary",
                  },
                  condition_hints: {
                    status_path: "result.status",
                    status_values: ["ok", "error"],
                    error_codes: ["LOG_ACCESS_DENIED"],
                    condition_templates: [
                      { label: "status == ok", expression: "{step}.output.result.status == 'ok'" },
                      { label: "status == error", expression: "{step}.output.result.status == 'error'" },
                      {
                        label: "error_code == LOG_ACCESS_DENIED",
                        expression: "{step}.output.result.error.code == 'LOG_ACCESS_DENIED'",
                      },
                    ],
                  },
                },
              ],
              scenario_templates: [
                {
                  key: "site_not_opening",
                  title: "Сайт не открывается",
                  problem: "site_not_opening",
                  recommended_form_keys: ["site_system"],
                  block_ids: ["system.collect", "diag.logs.collect"],
                },
              ],
              playbooks: [],
            },
          });
        }

        if (url === "/api/web/admin/playbooks/save" && method === "POST") {
          saveCalls.push(JSON.parse(String(init?.body ?? "{}")));
          return jsonResponse({
            status: "success",
            data: {
              key: "site_not_opening",
              version: "1.0.0",
              status: "published",
              blocks_count: 3,
              message: "Плейбук опубликован как версия 1.0.0.",
            },
          });
        }

        throw new Error(`Unexpected fetch ${method} ${url}`);
      }),
    );

    renderPanel();

    expect(await screen.findByText("Playbook Builder")).toBeInTheDocument();
    expect(await screen.findByText("Старт")).toBeInTheDocument();
    expect(await screen.findAllByText("Системный снимок")).not.toHaveLength(0);
    expect(await screen.findAllByText("Сбор логов")).not.toHaveLength(0);
    expect(await screen.findAllByText("result.status")).not.toHaveLength(0);
    expect(await screen.findAllByText("ok, error")).not.toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Блок условия" }));
    expect(screen.getByText("Проверка результата")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Quick condition template"), {
      target: { value: "steps.system_collect.output.result.status == 'ok'" },
    });

    const commandSelect = screen.getByLabelText("Команда блока Системный снимок");
    fireEvent.change(commandSelect, { target: { value: "diag.logs.collect" } });
    expect(await screen.findAllByLabelText("Блок Сбор логов")).not.toHaveLength(0);

    const movedBlock = screen.getAllByLabelText("Блок Сбор логов")[1];
    const canvas = movedBlock.closest(".playbook-canvas-grid") ?? document.querySelector(".playbook-canvas-grid");
    expect(canvas).toBeTruthy();
    fireEvent.dragStart(movedBlock, {
      dataTransfer: dataTransferStub({ "application/x-playbook-block": "diag_logs_collect" }),
    });
    fireEvent.drop(canvas as Element, {
      clientX: 480,
      clientY: 180,
      dataTransfer: dataTransferStub({ "application/x-playbook-block": "diag_logs_collect" }),
    });

    fireEvent.click(screen.getByRole("button", { name: "Опубликовать" }));

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });
    expect(saveCalls[0]).toMatchObject({
      key: "site_not_opening",
      blocks: [
        { tool: "diag.logs.collect", module_kind: "diagnostic" },
        { tool: "diag.logs.collect", module_kind: "diagnostic" },
        { type: "decision", module_kind: "diagnostic" },
      ],
    });
    expect(await screen.findByText("Плейбук опубликован как версия 1.0.0.")).toBeInTheDocument();
  });
});
