import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ProcessEditors } from "./process-editors";
import type { StudioDraft } from "./draft-model";

it("explains closure through the public result without requiring a resolution code", () => {
  const draft: StudioDraft = { serviceCode: "it", offeringCode: "print", templateCode: "print", title: "Печать", description: "", visibility: "public", processProfile: "", routingPolicyCode: "", slaPolicyCode: "", approvalMode: "none", approvalPolicyCode: "", closurePolicyCode: "", notificationPolicyCode: "", fields: [] };
  render(<ProcessEditors draft={draft} registry={null} showAutoFix={false} focusedBlockKey="closure" onDraftChange={vi.fn()} onShowAutoFixChange={vi.fn()} />);
  expect(screen.queryByText(/код решения, если это требует policy/)).not.toBeInTheDocument();
  expect(screen.getByText(/публичный итог решения/)).toBeVisible();
  expect(screen.getByRole("combobox", { name: "Правила закрытия" })).toBeVisible();
});
