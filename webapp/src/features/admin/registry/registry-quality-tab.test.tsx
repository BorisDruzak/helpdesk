import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RegistryQualityTab } from "./registry-quality-tab";

describe("RegistryQualityTab", () => {
  it("wires remediation actions and object selection for active quality issues", () => {
    const issue = {
      issue_key: "binding_inactive_person:binding:binding-1",
      kind: "binding_inactive_person",
      severity: "danger",
      title: "Active binding points to inactive person",
      description: "device-1",
      object_type: "binding",
      object_id: "binding-1",
      binding_id: "binding-1",
      device_id: "device-1",
      person_id: "person-1",
    } as const;
    const onFix = vi.fn();
    const onIgnore = vi.fn();
    const onSelect = vi.fn();
    const onSnooze = vi.fn();

    render(
      <RegistryQualityTab
        issues={[issue]}
        suggestions={[]}
        onFix={onFix}
        onIgnore={onIgnore}
        onSelect={onSelect}
        onSnooze={onSnooze}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Открыть" }));
    expect(onSelect).toHaveBeenCalledWith({ kind: "binding", id: "binding-1" });

    fireEvent.click(screen.getByRole("button", { name: "Исправить" }));
    expect(onFix).toHaveBeenCalledWith(issue);

    fireEvent.click(screen.getByRole("button", { name: "Игнорировать" }));
    expect(onIgnore).toHaveBeenCalledWith(issue);

    fireEvent.click(screen.getByRole("button", { name: "Отложить на 7 дней" }));
    expect(onSnooze).toHaveBeenCalledWith(issue, 7);
  });

  it("keeps remediation available for UI-user link issues without opening an unrelated object", () => {
    const issue = {
      issue_key: "ui_user_unlinked_registry_person:ui_user:phase8@example.test",
      kind: "ui_user_unlinked_registry_person",
      severity: "warning",
      title: "UI user is not linked to Registry person",
      description: "phase8@example.test",
      object_type: "ui_user",
      object_id: "phase8@example.test",
    } as const;
    const onFix = vi.fn();
    const onIgnore = vi.fn();
    const onSelect = vi.fn();
    const onSnooze = vi.fn();

    render(
      <RegistryQualityTab
        issues={[issue]}
        suggestions={[]}
        onFix={onFix}
        onIgnore={onIgnore}
        onSelect={onSelect}
        onSnooze={onSnooze}
      />
    );

    expect(screen.getByRole("button", { name: "Открыть" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Исправить" }));

    expect(onFix).toHaveBeenCalledWith(issue);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("surfaces audience and Knowledge visibility quality issues as actionable tasks", () => {
    const issues = [
      {
        issue_key: "audience_group_empty:audience_group:aud-1",
        kind: "audience_group_empty",
        severity: "warning",
        title: "Audience group has no people",
        description: "aud-1",
        object_type: "audience_group",
        object_id: "aud-1",
      },
      {
        issue_key: "knowledge_audience_rule_invalid_target:knowledge_audience_rule:rule-1",
        kind: "knowledge_audience_rule_invalid_target",
        severity: "danger",
        title: "Broken Knowledge audience rule",
        description: "rule-1",
        object_type: "knowledge_audience_rule",
        object_id: "rule-1",
      },
      {
        issue_key: "knowledge_audience_zero_users:knowledge_item:item-1",
        kind: "knowledge_audience_zero_users",
        severity: "warning",
        title: "Knowledge item has zero users",
        description: "item-1",
        object_type: "knowledge_item",
        object_id: "item-1",
      },
    ] as const;
    const onFix = vi.fn();

    render(
      <RegistryQualityTab
        issues={[...issues]}
        suggestions={[]}
        onFix={onFix}
        onIgnore={vi.fn()}
        onSelect={vi.fn()}
        onSnooze={vi.fn()}
      />
    );

    expect(screen.getAllByText("Аудиторная группа без участников").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Правило видимости Knowledge с недействительной целью").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Статья Knowledge доступна нулю пользователей").length).toBeGreaterThan(0);

    const fixButtons = screen.getAllByRole("button", { name: "Исправить" });
    expect(fixButtons).toHaveLength(3);
    fireEvent.click(fixButtons[0]);
    expect(onFix).toHaveBeenCalledWith(issues[0]);
  });
});
