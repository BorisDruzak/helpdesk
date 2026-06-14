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

    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(onSelect).toHaveBeenCalledWith({ kind: "binding", id: "binding-1" });

    fireEvent.click(screen.getByRole("button", { name: "Fix" }));
    expect(onFix).toHaveBeenCalledWith(issue);

    fireEvent.click(screen.getByRole("button", { name: "Ignore" }));
    expect(onIgnore).toHaveBeenCalledWith(issue);

    fireEvent.click(screen.getByRole("button", { name: "Snooze 7d" }));
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

    expect(screen.getByRole("button", { name: "Open" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Fix" }));

    expect(onFix).toHaveBeenCalledWith(issue);
    expect(onSelect).not.toHaveBeenCalled();
  });
});
