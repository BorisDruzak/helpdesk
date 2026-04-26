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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("PlaybookBuilderPanel", () => {
  it("builds a diagnostic playbook from reorderable low-code blocks", async () => {
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
                  description: "CPU, память, сеть и платформа",
                  default_params: { preset: "network" },
                  changes_device: false,
                  requires_confirmation: false,
                  output_contract: {
                    status: "ok|error",
                    found: {},
                    error_code: null,
                    attachments: [],
                  },
                },
                {
                  id: "diag.logs.collect",
                  label: "Сбор логов",
                  tool: "diag.logs.collect",
                  block_type: "diagnostic",
                  module_kind: "diagnostic",
                  description: "Архив логов",
                  default_params: { preset: "system", tail_lines: 500 },
                  changes_device: false,
                  requires_confirmation: true,
                  output_contract: {
                    status: "ok|error",
                    found: {},
                    error_code: null,
                    attachments: ["logs_zip"],
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

    expect(await screen.findByRole("heading", { name: "Конструктор плейбуков" })).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Сайт не открывается" }));
    expect(await screen.findByText("Системный снимок")).toBeInTheDocument();
    expect(await screen.findByText("Сбор логов")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Добавить условие" }));
    fireEvent.click(screen.getByRole("button", { name: "Поднять блок Сбор логов" }));
    fireEvent.click(screen.getByRole("button", { name: "Сохранить плейбук" }));

    await waitFor(() => {
      expect(saveCalls).toHaveLength(1);
    });
    expect(saveCalls[0]).toMatchObject({
      key: "site_not_opening",
      blocks: [
        { tool: "diag.logs.collect", module_kind: "diagnostic" },
        { tool: "system.collect", module_kind: "diagnostic" },
        { type: "decision", module_kind: "diagnostic" },
      ],
    });
    expect(await screen.findByText("Плейбук опубликован как версия 1.0.0.")).toBeInTheDocument();
  });
});
