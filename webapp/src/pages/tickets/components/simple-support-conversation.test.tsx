import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { SupportTicketDetailPayload } from "../../../features/queues/api";
import { mapSupportTimelineEntries } from "../../../features/queues/support-workspace-mappers";
import { SimpleSupportConversation } from "./simple-support-conversation";

const raw = (extra: Record<string, unknown>) => ({ event_type: "chat_message", visibility: "public", text: "Здравствуйте", attachments: [], from_role: "support", message_id: null, event_id: null, ts: null, direction: "to_agent", reply_to: null, ...extra }) as SupportTicketDetailPayload["timeline"][number];

describe("clean support conversation", () => {
  const imageProps = (attachment: Record<string, unknown>) => ({items: mapSupportTimelineEntries([raw({event_id: 55, attachments: [attachment]})]), text: "", onTextChange: vi.fn(), onModeChange: vi.fn(), mode: "public" as const, canReply: true, canNote: true, onSend: vi.fn(), pending: false, attachments: [], onRemoveAttachment: vi.fn()});
  it("opens a screenshot in the current page and keeps download as an explicit action", () => {
    render(<SimpleSupportConversation {...imageProps({artifact_id: "image-1", name: "Ошибка.png", mime_type: "image/png", url: "/api/artifacts/image-1/download"})} />);
    const thumbnail = screen.getByRole("img", {name: "Миниатюра: Ошибка.png"});
    expect(thumbnail).toHaveAttribute("src", "/api/artifacts/image-1/download");
    fireEvent.click(screen.getByRole("button", {name: "Открыть изображение Ошибка.png"}));
    const dialog = screen.getByRole("dialog", {name: "Просмотр изображения: Ошибка.png"});
    expect(dialog).toBeVisible();
    expect(screen.getByRole("link", {name: "Скачать Ошибка.png"})).toHaveAttribute("download");
    fireEvent.click(screen.getByRole("button", {name: "Закрыть просмотр изображения"}));
    fireEvent(dialog, new Event("close"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
  it.each(["https://foreign.test/private.png", "//foreign.test/private.png", "/api/artifacts/image-1/download?token=secret", "/other/image.png"])("does not load untrusted image URL %s", (url) => {
    render(<SimpleSupportConversation {...imageProps({name: "Ошибка.png", mime_type: "image/png", url})} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", {name: /Открыть изображение/})).not.toBeInTheDocument();
  });
  it("preserves the canonical legacy ticket scope for preview and download", () => {
    const url = "/api/artifacts/legacy-image/download?ticket_id=ticket-1";
    render(<SimpleSupportConversation {...imageProps({artifact_id: "legacy-image", name: "История.png", url})} />);
    expect(screen.getByRole("img", {name: "Миниатюра: История.png"})).toHaveAttribute("src", url);
    expect(screen.getByRole("link", {name: "Скачать История.png"})).toHaveAttribute("href", url);
  });
  it.each(["image/svg+xml", "text/html", "application/pdf"])("does not embed %s even with a misleading raster filename", (mime_type) => {
    render(<SimpleSupportConversation {...imageProps({artifact_id: "doc", name: "Ошибка.png", mime_type, url: "/api/artifacts/doc/download"})} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("link", {name: "Ошибка.png"})).toBeInTheDocument();
  });
  it("keeps download available when the full image cannot be decoded", () => {
    render(<SimpleSupportConversation {...imageProps({artifact_id: "bad", name: "Ошибка.png", url: "/api/artifacts/bad/download"})} />);
    fireEvent.click(screen.getByRole("button", {name: "Открыть изображение Ошибка.png"}));
    fireEvent.error(screen.getByRole("img", {name: "Ошибка.png"}));
    expect(screen.getByText("Не удалось открыть изображение. Попробуйте скачать файл.")).toBeVisible();
    expect(screen.getByRole("link", {name: "Скачать изображение"})).toHaveAttribute("href", "/api/artifacts/bad/download");
  });
  it("keeps non-image attachments as downloads and explains an unavailable thumbnail", () => {
    const view = render(<SimpleSupportConversation {...imageProps({artifact_id: "doc", name: "Инструкция.pdf", mime_type: "application/pdf", url: "/api/artifacts/doc/download"})} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("link", {name: "Инструкция.pdf"})).toBeInTheDocument();
    view.rerender(<SimpleSupportConversation {...imageProps({artifact_id: "bad", name: "Ошибка.png", url: "/api/artifacts/bad/download"})} />);
    fireEvent.error(screen.getByRole("img", {name: "Миниатюра: Ошибка.png"}));
    expect(screen.getByText("Миниатюра недоступна")).toBeVisible();
    expect(screen.getByRole("link", {name: "Скачать Ошибка.png"})).toBeInTheDocument();
  });
  it("requests the matching server stream when switching dialogue, notes and history", () => {
    const changed = vi.fn();
    render(<SimpleSupportConversation items={[]} text="" onTextChange={vi.fn()} onModeChange={vi.fn()} onTabChange={changed} mode="public" canReply canNote onSend={vi.fn()} pending={false} attachments={[]} onRemoveAttachment={vi.fn()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Внутренние заметки" }));
    expect(changed).toHaveBeenLastCalledWith("internal");
    fireEvent.click(screen.getByRole("tab", { name: "История" }));
    expect(changed).toHaveBeenLastCalledWith("all");
    fireEvent.click(screen.getByRole("tab", { name: "Диалог" }));
    expect(changed).toHaveBeenLastCalledWith("messages");
  });
  it("preserves reading position when a new message arrives and can return to the latest", () => {
    const props = { items: mapSupportTimelineEntries([raw({ event_id: 1 })]), text: "", onTextChange: vi.fn(), onModeChange: vi.fn(), mode: "public" as const, canReply: true, canNote: true, onSend: vi.fn(), pending: false, attachments: [], onRemoveAttachment: vi.fn() };
    const view = render(<SimpleSupportConversation {...props} />);
    const feed = screen.getByRole("tabpanel", { name: "Диалог" });
    Object.defineProperties(feed, { scrollHeight: { value: 1600 }, clientHeight: { value: 400 } });
    feed.scrollTop = 120;
    fireEvent.scroll(feed);
    view.rerender(<SimpleSupportConversation {...props} items={mapSupportTimelineEntries([raw({ event_id: 1 }), raw({ event_id: 2, text: "Новое сообщение" })])} />);
    expect(feed.scrollTop).toBe(120);
    fireEvent.click(screen.getByRole("button", { name: "К новым сообщениям" }));
    expect(feed.scrollTop).toBe(1600);
    expect(screen.queryByRole("button", { name: "К новым сообщениям" })).not.toBeInTheDocument();
  });
  it("sends with Ctrl+Enter, keeps plain Enter for multiline, and explains the server denial", () => {
    const send = vi.fn();
    const props = { items: [], text: "Ответ", onTextChange: vi.fn(), onModeChange: vi.fn(), mode: "public" as const, canReply: true, canNote: true, onSend: send, pending: false, attachments: [], onRemoveAttachment: vi.fn(), replyBlockedReason: "Вы не состоите в очереди обращения." };
    const view = render(<SimpleSupportConversation {...props} />);
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(send).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", ctrlKey: true });
    expect(send).toHaveBeenCalledTimes(1);
    view.rerender(<SimpleSupportConversation {...props} canReply={false} />);
    expect(screen.getByText(props.replyBlockedReason)).toBeVisible();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter", ctrlKey: true });
    expect(send).toHaveBeenCalledTimes(1);
  });
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
