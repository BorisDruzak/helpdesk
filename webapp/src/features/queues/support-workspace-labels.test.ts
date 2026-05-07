import { describe, expect, it } from "vitest";

import {
  externalProviderStatusLabel,
  fallbackReasonLabel,
  operationActionReasonSentence,
  operationPolicyLabel,
  permissionMetaLabel,
  providerStatusLabel,
  riskMetaLabel,
} from "./support-workspace-labels";

describe("support workspace labels", () => {
  it("maps policy and permission codes to operator-facing labels", () => {
    expect(permissionMetaLabel("module.tool.run.low_risk")).toBe("Право: запуск безопасных инструментов");
    expect(riskMetaLabel("safe_readonly")).toBe("Риск: безопасное чтение");
    expect(operationPolicyLabel("permission:ticket.queue.change")).toBe("Право: смена очереди");
    expect(operationPolicyLabel("retry:CONSENT_REQUIRED_FOR_RETRY")).toBe(
      "Повтор: для повтора нужно новое согласие пользователя",
    );
  });

  it("maps disabled operation reasons into clear tooltip text", () => {
    expect(operationActionReasonSentence("retry_params_unavailable")).toBe(
      "Нет безопасно сохранённых параметров повтора",
    );
    expect(operationActionReasonSentence("status_not_cancelable")).toBe("Текущий статус нельзя отменить");
  });

  it("maps knowledge diagnostics statuses without leaking raw provider codes as labels", () => {
    expect(providerStatusLabel("provider_unavailable")).toBe("провайдер недоступен");
    expect(externalProviderStatusLabel("not_configured")).toBe("не подключена");
    expect(fallbackReasonLabel("catalog_fallback")).toBe("использован локальный каталог");
  });
});
