import { describe, expect, it } from "vitest";

import {
  formatHumanIdentifier,
  formatRussianDate,
  formatRussianDateTime,
  formatStatusLabel,
  statusBadgeTone,
} from "./formatters";

describe("ui-page formatters", () => {
  it("formats dates in a stable Russian numeric form", () => {
    const value = "2026-06-19T12:34:56.000Z";

    expect(formatRussianDate(value, { timeZone: "UTC" })).toBe("19.06.2026");
    expect(formatRussianDateTime(value, { timeZone: "UTC" })).toBe("19.06.2026, 12:34");
  });

  it("maps technical statuses to Russian labels and badge tones", () => {
    expect(formatStatusLabel("open")).toBe("Открыта");
    expect(formatStatusLabel("in_progress")).toBe("В работе");
    expect(formatStatusLabel("waiting_user")).toBe("Ждет пользователя");
    expect(formatStatusLabel("not_a_known_status")).toBe("not a known status");

    expect(statusBadgeTone("open")).toBe("info");
    expect(statusBadgeTone("resolved")).toBe("success");
    expect(statusBadgeTone("pending")).toBe("warning");
    expect(statusBadgeTone("canceled")).toBe("danger");
  });

  it("keeps human codes readable and masks raw UUIDs", () => {
    expect(formatHumanIdentifier("REQ-2042")).toBe("REQ-2042");
    expect(formatHumanIdentifier("550e8400-e29b-41d4-a716-446655440000")).toBe("ID 550e8400");
    expect(formatHumanIdentifier(null, { emptyText: "Нет кода" })).toBe("Нет кода");
  });
});
