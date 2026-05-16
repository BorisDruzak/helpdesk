import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QueryProvider } from "../../app/providers/query-provider";
import { evaluateKnowledgeSubmitGate, HelpPage, visibleKnowledgeSuggestions } from "./index";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function renderHelpPage() {
  render(
    <QueryProvider>
      <MemoryRouter>
        <HelpPage />
      </MemoryRouter>
    </QueryProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HelpPage", () => {
  it("applies no-suggestions, API-unavailable, min-suggestions and urgent bypass policy", () => {
    expect(
      evaluateKnowledgeSubmitGate({
        rollout: {
          require_suggestions_before_submit: true,
          allow_skip: false,
          min_suggestions: 1,
          no_suggestions_behavior: "block_submit",
        },
        suggestionsLoaded: true,
        suggestionCount: 0,
      }),
    ).toMatchObject({ canSubmit: false, reason: "no_suggestions_block" });

    expect(
      evaluateKnowledgeSubmitGate({
        rollout: {
          require_suggestions_before_submit: true,
          allow_skip: false,
          min_suggestions: 2,
          no_suggestions_behavior: "block_submit",
        },
        suggestionsLoaded: true,
        suggestionCount: 1,
      }),
    ).toMatchObject({ canSubmit: false, reason: "min_suggestions_block" });

    expect(
      evaluateKnowledgeSubmitGate({
        rollout: {
          require_suggestions_before_submit: true,
          allow_skip: false,
          api_unavailable_behavior: "show_warning",
        },
        apiUnavailable: true,
        suggestionsLoaded: true,
        suggestionCount: 0,
      }),
    ).toMatchObject({ canSubmit: true, warning: true, reason: "api_unavailable_warning" });

    expect(
      evaluateKnowledgeSubmitGate({
        rollout: {
          require_suggestions_before_submit: true,
          allow_skip: false,
          min_suggestions: 2,
          no_suggestions_behavior: "block_submit",
          bypass_applied: true,
        },
        suggestionsLoaded: true,
        suggestionCount: 0,
      }),
    ).toMatchObject({ canSubmit: true, reason: "bypass" });
  });

  it("hides known-error suggestions and safe labels according to rollout", () => {
    const items = visibleKnowledgeSuggestions(
      [
        { item_id: "known", slug: "known", type: "known_error", title: "Known", quality_label: "Verified" },
        { item_id: "article", slug: "article", type: "article", title: "Article", freshness_label: "Fresh" },
      ],
      {
        show_known_errors: false,
        show_quality_badge: false,
        show_review_freshness: false,
      },
    );

    expect(items).toEqual([{ item_id: "article", slug: "article", type: "article", title: "Article" }]);
  });

  it("creates a public ticket from the selected request form", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/public_api/ticket_forms/current?pack_key=request_forms") {
        return jsonResponse({
          status: "ok",
          pack: {
            pack_key: "request_forms",
            version: "1.2.0",
            forms: [
              {
                key: "site_down",
                title: "Сайт не открывается",
                request_kind: "site_down",
                fields: [
                  {
                    key: "url",
                    label: "Адрес сайта",
                    type: "text",
                    required: true,
                    placeholder: "https://example.com",
                  },
                ],
              },
            ],
          },
        });
      }
      if (url === "/public_api/tickets/create") {
        expect(init?.method).toBe("POST");
        expect(JSON.parse(String(init?.body))).toMatchObject({
          title: "Заявка: Сайт не открывается",
          description: "Не открывается портал",
          user_display_name: "Иван",
          form_key: "site_down",
          form_pack_key: "request_forms",
          form_pack_version: "1.2.0",
          form_payload: {
            url: "https://intranet.local",
          },
          ticket_type: "site_down",
          urgency: false,
          importance: false,
          urgency_reason: "requester_did_not_mark_urgent",
          importance_reason: "requester_did_not_mark_important",
        });
        return jsonResponse({
          status: "ok",
          ticket: { ticket_id: "T-100", ticket_code: "HD-100", status: "new" },
          public_access_code: "A1B2C3",
          public_token: "token-100",
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock as typeof fetch);

    renderHelpPage();

    expect(await screen.findByRole("heading", { name: "Создать заявку" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Как к вам обращаться"), { target: { value: "Иван" } });
    fireEvent.change(screen.getByLabelText("Описание проблемы"), { target: { value: "Не открывается портал" } });

    fireEvent.click(screen.getByRole("button", { name: "Создать заявку" }));
    expect(await screen.findByText(/Заполните обязательные поля: Адрес сайта/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Адрес сайта *"), { target: { value: "https://intranet.local" } });
    fireEvent.click(screen.getByRole("button", { name: "Создать заявку" }));

    expect(await screen.findByText("Код доступа: A1B2C3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Открыть тикет" })).toHaveAttribute(
      "href",
      "/app/ticket/T-100?code=A1B2C3",
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });
});
