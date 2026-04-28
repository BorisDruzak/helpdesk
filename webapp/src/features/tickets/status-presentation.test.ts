import { describe, expect, it } from "vitest";

import {
  getNextActionOwnerLabel,
  getTicketStatusPresentation,
  getTicketStatusTone,
} from "./status-presentation";

describe("ticket status presentation", () => {
  it("maps canonical waiting statuses to predictable operator labels", () => {
    const presentation = getTicketStatusPresentation({
      status: "waiting_on_vendor",
      statusLabel: "Ожидает внешнюю сторону",
      requesterStatusLabel: "В работе",
      nextActionOwner: "vendor",
      statusReason: "Провайдер подтвердит замену",
      evidenceRequired: true,
      evidenceRef: null,
    });

    expect(presentation.tone).toBe("warning");
    expect(presentation.stageLabel).toBe("Ожидание");
    expect(presentation.statusLabel).toBe("Ожидает внешнюю сторону");
    expect(presentation.requesterStatusLabel).toBe("В работе");
    expect(presentation.ownerLabel).toBe("Внешняя сторона");
    expect(presentation.operatorActionLabel).toBe("Контролировать внешний ответ");
    expect(presentation.evidenceLabel).toBe("Нужно доказательство");
    expect(presentation.evidenceTone).toBe("warning");
    expect(presentation.waits).toBe(true);
    expect(presentation.terminal).toBe(false);
  });

  it("marks resolved and closed statuses as terminal with evidence readiness", () => {
    expect(getTicketStatusPresentation({
      status: "resolved",
      statusLabel: "Решён",
      requesterStatusLabel: "Решён",
      nextActionOwner: "requester",
      statusReason: null,
      evidenceRequired: true,
      evidenceRef: "operation-42",
    })).toMatchObject({
      tone: "success",
      stageLabel: "Решение",
      ownerLabel: "Пользователь",
      operatorActionLabel: "Ждать подтверждение результата",
      evidenceLabel: "Доказательство есть",
      evidenceTone: "success",
      terminal: true,
    });

    expect(getTicketStatusPresentation({
      status: "closed",
      statusLabel: "Закрыт",
      requesterStatusLabel: "Закрыт",
      nextActionOwner: "support",
      statusReason: null,
      evidenceRequired: false,
      evidenceRef: null,
    })).toMatchObject({
      tone: "neutral",
      stageLabel: "Закрыт",
      operatorActionLabel: "Контроль не требуется",
      evidenceLabel: "Не требуется",
      terminal: true,
    });
  });

  it("keeps unknown values visible without breaking the UI", () => {
    expect(getTicketStatusTone("custom_status")).toBe("neutral");
    expect(getNextActionOwnerLabel("external_partner")).toBe("external_partner");
    expect(getTicketStatusPresentation({
      status: "custom_status",
      statusLabel: "",
      requesterStatusLabel: "",
      nextActionOwner: null,
      statusReason: null,
      evidenceRequired: false,
      evidenceRef: null,
    })).toMatchObject({
      statusLabel: "custom_status",
      requesterStatusLabel: "Не указан",
      ownerLabel: "Не указан",
      stageLabel: "Другое",
      operatorActionLabel: "Проверить карточку",
    });
  });
});
