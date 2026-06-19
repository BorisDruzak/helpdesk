import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RequesterConsentList } from "./consent-card";
import type { RequesterConsent } from "./types";

const baseConsent: RequesterConsent = {
  consent_id: "consent-screen-view",
  subject_type: "remote_assist",
  subject_id: "remote-assist-screen-view",
  status: "pending",
  ticket_id: "550e8400-e29b-41d4-a716-446655440000",
  requester_person_id: "person-requester",
  requester_binding_id: "binding-requester",
  requester_account_session_id: "session-requester",
  requested_by_actor_id: "support-operator-1",
  requested_by_role: "support",
  risk_level: "remote_view",
  title: "Разрешить просмотр экрана",
  description: "Специалист просит временный просмотр экрана для обращения.",
  reason: "Нужно увидеть ошибку на экране.",
  expires_at: "2026-06-20T10:00:00Z",
  requested_action_payload_redacted: {
    session_id: "remote-session-secret",
    mode: "view_only",
    duration_minutes: 5,
  },
};

describe("RequesterConsentList", () => {
  it("explains requester-safe consent details without visible or accessible technical identifiers", () => {
    render(
      <RequesterConsentList
        consents={[
          baseConsent,
          {
            ...baseConsent,
            consent_id: "consent-diagnostic",
            subject_type: "operation",
            subject_id: "diag-raw-id",
            risk_level: "diagnostic",
            title: "Диагностика устройства",
            description: "Специалист просит выполнить безопасную диагностику.",
            requested_action_payload_redacted: { tool_name: "observer_canary.consent_probe" },
          },
          {
            ...baseConsent,
            consent_id: "consent-control",
            risk_level: "remote_control",
            title: "Удаленное управление",
            requested_action_payload_redacted: { mode: "interactive_control", duration_minutes: 10 },
          },
          {
            ...baseConsent,
            consent_id: "consent-admin",
            risk_level: "remote_admin",
            title: "Административный доступ",
            requested_action_payload_redacted: { mode: "elevated_admin", duration_minutes: 3 },
          },
        ]}
        onDecision={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Ожидают вашего решения" })).toBeInTheDocument();
    expect(screen.getAllByText("Просмотр экрана").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Диагностика").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Удаленное управление").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Административный доступ").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Обращение 550e8400").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Для: текущий заявитель").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Запросил: специалист поддержки").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/До:/).length).toBeGreaterThan(0);

    const text = document.body.textContent ?? "";
    expect(text).toContain("Причина: Нужно увидеть ошибку на экране.");
    expect(text).not.toContain("consent-screen-view");
    expect(text).not.toContain("remote-assist-screen-view");
    expect(text).not.toContain("remote-session-secret");
    expect(text).not.toContain("person-requester");
    expect(text).not.toContain("binding-requester");
    expect(text).not.toContain("session-requester");
    expect(text).not.toContain("support-operator-1");
    expect(screen.queryByLabelText(/consent/i)).not.toBeInTheDocument();
  });

  it("locks the selected card while a decision is pending", async () => {
    let resolveDecision!: () => void;
    const onDecision = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          resolveDecision = resolve;
        }),
    );

    render(<RequesterConsentList consents={[baseConsent]} onDecision={onDecision} />);

    const card = screen.getByRole("article", { name: "Разрешить просмотр экрана" });
    const approve = within(card).getByRole("button", { name: "Разрешить запрос согласия" });

    fireEvent.click(approve);
    fireEvent.click(approve);

    expect(onDecision).toHaveBeenCalledTimes(1);
    expect(approve).toBeDisabled();

    resolveDecision();
    await waitFor(() => expect(approve).not.toBeDisabled());
  });
});
