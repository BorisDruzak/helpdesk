import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { SupportWorkspaceTimelineItem } from "../../../features/queues/support-workspace-model";
import { partitionSupportTimeline } from "../../../features/queues/support-conversation";
import { SupportConversationTimeline } from "./SupportConversationTimeline";

afterEach(cleanup);
function item(id: string, kind: SupportWorkspaceTimelineItem["kind"], body: string): SupportWorkspaceTimelineItem {
  return { id, kind, body, title: "Сообщение", actor: "Участник", timestampLabel: "12:30", visibility: kind === "internal" ? "internal" : "public", tone: "brand", attachments: [] };
}
it("shows human public and internal replies with their attachments while moving system context out of chat", () => {
  const onOpenContext = vi.fn();
  render(<SupportConversationTimeline onOpenContext={onOpenContext} items={[
    item("user", "message", "Принтер не печатает"),
    item("route", "history", "Назначена очередь и SLA"),
    { ...item("note", "internal", "Проверяю связь с принтером"), attachments: [{ artifact_id: "human-evidence" }] },
    item("tool", "diagnostics", "Диагностика завершена"),
    item("access", "history", "Код доступа сформирован"),
  ]} />);
  const conversation = screen.getByRole("region", { name: "Переписка" });
  expect(within(conversation).getByText("Принтер не печатает")).toBeVisible();
  expect(within(conversation).getByText("Проверяю связь с принтером")).toBeVisible();
  expect(within(conversation).getByText("1 влож.")).toBeVisible();
  expect(within(conversation).queryByText("Назначена очередь и SLA")).not.toBeInTheDocument();
  expect(within(conversation).queryByText("Диагностика завершена")).not.toBeInTheDocument();
  expect(within(conversation).queryByText("Код доступа сформирован")).not.toBeInTheDocument();
  expect(screen.getByText("Системные события и диагностика: 3")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Открыть контекст" })); expect(onOpenContext).toHaveBeenCalledOnce();
});
it("explains an empty human conversation without turning lifecycle events into chat bubbles", () => {
  render(<SupportConversationTimeline items={[item("accepted", "history", "Обращение принято в работу")]} />);
  expect(screen.getByText("Сообщений пользователя и поддержки пока нет.")).toBeVisible();
  expect(screen.queryByRole("article")).not.toBeInTheDocument();
  expect(screen.getByText("Системные события и диагностика: 1")).toBeVisible();
  expect(screen.queryByRole("button", { name: "Открыть контекст" })).not.toBeInTheDocument();
});
it("preserves the complete context and diagnostic payload in original order for the parent panel", () => {
  const diagnostic = { ...item("tool", "diagnostics", "Результат"), operation: { name: "system.collect", status: "completed", statusLabel: "Готово", statusTone: "success" as const, summary: "Собрано", preview: null, resultPayload: { hostname: "test-device" }, metaLabels: [] } };
  const history = { ...item("history", "history", "SLA назначен"), attachments: [{ artifact_id: "context-evidence" }] };
  const message = item("human", "message", "Спасибо");
  const partition = partitionSupportTimeline([diagnostic, message, history]);
  expect(partition.conversation).toEqual([message]);
  expect(partition.context).toEqual([diagnostic, history]);
  expect(partition.context[0]).toBe(diagnostic); expect(partition.context[1]).toBe(history);
});
