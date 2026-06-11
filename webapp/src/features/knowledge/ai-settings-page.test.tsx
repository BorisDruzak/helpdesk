import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeAiSettingsPage } from "./ai-settings-page";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <KnowledgeAiSettingsPage />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("KnowledgeAiSettingsPage", () => {
  it("renders Russian AI settings with masked secret state and safe audit", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/web/knowledge/ai/providers") {
        return jsonResponse({
          status: "ok",
          providers: [
            {
              provider_id: "provider-1",
              code: "openrouter-main",
              title: "OpenRouter",
              provider_type: "openrouter",
              base_url: "https://openrouter.ai/api/v1",
              data_policy: "no_sensitive",
              enabled: true,
              health_status: "failed",
              api_key_configured: true,
              api_key_secret_ref_masked: "env:OPEN...KEY",
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/ai/model-profiles") {
        return jsonResponse({
          status: "ok",
          model_profiles: [
            {
              profile_id: "profile-1",
              provider_id: "provider-1",
              code: "answer-default",
              title: "Ответы через OpenRouter",
              task_type: "answer",
              model_name: "openai/gpt-4o-mini",
              enabled: true,
              is_default: true,
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/ai/policies") {
        return jsonResponse({
          status: "ok",
          policies: [
            {
              policy_id: "policy-1",
              scope_type: "global",
              enabled: true,
              ai_allowed: false,
              embedding_allowed: false,
              rerank_allowed: false,
              answer_allowed: false,
              rewrite_allowed: false,
              auto_markup_allowed: false,
              redact_before_send: true,
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/ai/audit") {
        return jsonResponse({
          status: "ok",
          display_message: "Журнал AI загружен",
          audit: [
            {
              audit_id: "audit-1",
              provider_id: "provider-1",
              task_type: "health_check",
              status: "failed",
              error_code: "SECRET_NOT_CONFIGURED",
              error_message_redacted: "<redacted>",
              created_at: "2026-06-11T10:00:00Z",
            },
          ],
        });
      }
      if (url === "/api/web/knowledge/ai/providers/provider-1/health-check" && init?.method === "POST") {
        return jsonResponse({
          status: "ok",
          display_message: "Ключ OpenRouter не настроен",
          health: { provider_id: "provider-1", status: "failed", error_code: "SECRET_NOT_CONFIGURED" },
        });
      }
      throw new Error(`Unexpected fetch ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Настройки AI для базы знаний" })).toBeInTheDocument();
    expect(await screen.findByText(/env:OPEN\.\.\.KEY/)).toBeInTheDocument();
    expect(screen.getByText("Провайдеры")).toBeInTheDocument();
    expect(screen.getByText("Профили моделей")).toBeInTheDocument();
    expect(screen.getByText("Политики AI")).toBeInTheDocument();
    expect(screen.getByText("Журнал AI")).toBeInTheDocument();
    expect(screen.getByText("Ответы через OpenRouter")).toBeInTheDocument();
    expect(screen.getByText("AI выключен")).toBeInTheDocument();
    expect(screen.getByText("<redacted>")).toBeInTheDocument();

    const visibleText = document.body.textContent ?? "";
    expect(visibleText).not.toContain("OPENROUTER_API_KEY");
    expect(visibleText).not.toContain("sk-");
    expect(visibleText).not.toContain("Рџ");

    fireEvent.click(screen.getByRole("button", { name: "Проверить OpenRouter" }));
    await waitFor(() => expect(screen.getByText("Ключ OpenRouter не настроен")).toBeInTheDocument());
  });
});
