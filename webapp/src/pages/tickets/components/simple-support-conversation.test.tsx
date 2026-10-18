import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import { mapSupportTimelineEntries } from "../../../features/queues/support-workspace-mappers";
import { SimpleSupportConversation } from "./simple-support-conversation";

const raw = (extra: Record<string, unknown>) => ({ event_type: "chat_message", visibility: "public", text: "Здравствуйте", attachments: [], from_role: "support", message_id: null, event_id: null, ts: null, direction: "to_agent", reply_to: null, ...extra }) as SupportTicketDetailPayload["timeline"][number];

describe("clean support conversation", () => {
  it("puts internal diagnostic and status events in history rather than operator notes", () => {
    const items = mapSupportTimelineEntries([
      raw({ event_id: 20, event_type: "tool_call_result", visibility: "internal" }),
      raw({ event_id: 21, event_type: "status_changed", visibility: "internal" }),
    ]);
    expect(items.map((item) => item.kind)).toEqual(["diagnostics", "history"]);
  });

  it("keeps distinct message and event identities even when their printed values coincide", () => {
    const items = mapSupportTimelineEntries([raw({ message_id: "1", event_id: 7 }), raw({ event_id: 1, visibility: "system", text: "Статус изменён" })]);
    expect(new Set(items.map((item) => item.id)).size).toBe(2);
  });

  it("deduplicates stable identities, keeps attachments and moves technical chat events to history", () => {
    const items = mapSupportTimelineEntries([
      raw({ event_id: 1, message_id: "m1" }), raw({ event_id: 1, attachments: [{ artifact_id: "a1", filename: "Ошибка.png" }] }),
      raw({ event_id: 2, visibility: "system", text: "SLA рассчитан" }),
      raw({ event_id: 3, visibility: "internal", text: "Заметка коллегам" }),
      raw({ event_id: 4, message_id: "confirm", text: "Подтвердите решение" }),
      raw({ event_id: 5, from_role: "system", text: "Исполнитель изменён автоматически" }),
    ]);
    expect(items).toHaveLength(5);
    expect(items.find((item) => item.body === "Здравствуйте")?.attachments).toHaveLength(1);
    expect(items.find((item) => item.body === "SLA рассчитан")?.kind).toBe("history");
    expect(items.find((item) => item.body === "Исполнитель изменён автоматически")?.kind).toBe("history");
    render(<SimpleSupportConversation items={items} text="" onTextChange={vi.fn()} onModeChange={vi.fn()} mode="public" canReply={false} canNote onSend={vi.fn()} pending={false} attachments={[]} onRemoveAttachment={vi.fn()} />);
    expect(screen.getByText("Здравствуйте")).toBeInTheDocument();
    expect(screen.getByText("Подтвердите решение")).toBeInTheDocument();
    expect(screen.queryByText("SLA рассчитан")).not.toBeInTheDocument();
    expect(screen.queryByText("Заметка коллегам")).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Сообщение сотруднику" })).toBeDisabled();
    fireEvent.click(screen.getByRole("tab", { name: "Внутренние заметки" }));
    expect(screen.getByText("Заметка коллегам")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "История" }));
    expect(screen.getByText("SLA рассчитан")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Шаблоны" })).not.toBeInTheDocument();
  });
});
