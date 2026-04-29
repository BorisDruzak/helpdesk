import { describe, expect, it } from "vitest";

import {
  getMissingPermissionReason,
  hasAnyPermission,
  hasPermission,
  requirePermission,
} from "./permissions";

describe("permission helpers", () => {
  const session = {
    user_login: "op1",
    actor_role: "support",
    auth_type: "ui_token",
    default_workspace: "support",
    available_workspaces: ["support"],
    permissions: ["ticket.status.change", "ticket.comment.public"],
  };

  it("checks effective session permissions without role shortcuts", () => {
    expect(hasPermission(session, "ticket.status.change")).toBe(true);
    expect(hasPermission(session, "admin.modules.author")).toBe(false);
    expect(hasAnyPermission(session, ["admin.modules.author", "ticket.comment.public"])).toBe(true);
  });

  it("returns an operator-facing disabled reason", () => {
    expect(requirePermission(session, "ticket.comment.public").allowed).toBe(true);
    expect(requirePermission(session, "ticket.tool.run")).toEqual({
      allowed: false,
      reason: "Недостаточно прав: ticket.tool.run",
    });
    expect(getMissingPermissionReason("admin.forms.publish")).toBe("Недостаточно прав: admin.forms.publish");
  });
});
