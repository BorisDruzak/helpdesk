import { describe, expect, it } from "vitest";

import { summarizeToolAvailability } from "./tool-availability";

describe("summarizeToolAvailability", () => {
  it("groups available tools first and summarizes repeated offline reasons", () => {
    const summary = summarizeToolAvailability([
      {
        id: "playbook:printer",
        kind: "playbook",
        title: "Диагностика принтера",
        subtitle: "Проверка очереди печати",
        riskLabel: "low",
        enabled: false,
        disabledReason: "агент устройства offline",
        requiresConsent: false,
        metaLabels: [],
      },
      {
        id: "tool:dns",
        kind: "tool",
        title: "DNS",
        subtitle: "Проверка имени",
        riskLabel: "low",
        enabled: true,
        disabledReason: null,
        requiresConsent: false,
        metaLabels: [],
      },
      {
        id: "tool:collect",
        kind: "tool",
        title: "Сбор фактов",
        subtitle: "Inventory",
        riskLabel: "medium",
        enabled: false,
        disabledReason: "агент устройства offline",
        requiresConsent: false,
        metaLabels: [],
      },
    ]);

    expect(summary.available.map((item) => item.id)).toEqual(["tool:dns"]);
    expect(summary.unavailable.map((item) => item.id)).toEqual(["playbook:printer", "tool:collect"]);
    expect(summary.offlineUnavailableCount).toBe(2);
    expect(summary.dominantOfflineReason).toBe("агент устройства offline");
    expect(summary.allUnavailable).toBe(false);
  });
});
