import { describe, expect, it } from "vitest";

import {
  requesterAccessStatusLabel,
  requesterDeviceConnectionStatusLabel,
  requesterDeviceLabel,
  requesterDeviceSystemLabel,
  requesterErrorMessage,
  requesterReadinessText,
  requesterRelationshipLabel,
  requesterTicketNextActionLabel,
} from "./labels";

describe("requester labels", () => {
  it("formats devices without exposing raw identifiers", () => {
    expect(requesterDeviceLabel({ device_id: "550e8400-e29b-41d4-a716-446655440000" })).toBe("Устройство без имени");
    expect(requesterDeviceLabel({ asset_name: "Ноутбук бухгалтера", hostname: "LAP-42" })).toBe("Ноутбук бухгалтера · LAP-42");
    expect(requesterDeviceSystemLabel({ os: "Windows", agent_version: "3.1.72" })).toBe("Windows · Агент 3.1.72");
  });

  it("centralizes requester statuses and fallbacks", () => {
    expect(requesterRelationshipLabel("primary_user")).toBe("Основное устройство");
    expect(requesterAccessStatusLabel("pending_admin_review")).toBe("Ожидает проверки администратора");
    expect(requesterDeviceConnectionStatusLabel({ online: false })).toBe("Не в сети");
    expect(requesterReadinessText(false, false)).toBe("Профиль нужно заполнить");
    expect(requesterReadinessText(true, false)).toBe("Устройство не привязано");
    expect(requesterReadinessText(true, true)).toBe("Можно создавать обращения");
  });

  it("formats errors and next actions through safe Russian copy", () => {
    expect(requesterErrorMessage(null, "Не удалось загрузить кабинет")).toBe("Не удалось загрузить кабинет");
    expect(requesterErrorMessage(new Error("Нет доступа"), "Не удалось загрузить кабинет")).toBe("Нет доступа");
    expect(requesterTicketNextActionLabel({ ticket_id: "T-1", status: "waiting_user" })).toBe("Нужен ваш ответ");
    expect(requesterTicketNextActionLabel({ ticket_id: "T-2", status: "resolved" })).toBe("Подтвердите решение");
  });
});
