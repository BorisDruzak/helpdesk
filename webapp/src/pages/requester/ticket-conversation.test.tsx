import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { RequesterConversation } from "./ticket-conversation";

afterEach(cleanup);
it("previews requester and support screenshots in the chat with separate downloads", () => {
  render(<RequesterConversation messages={[
    {event_id: "owner-image", from_role: "user", attachments: [{artifact_id: "owner-image", name: "Моя ошибка.png", mime_type: "image/png"}]},
    {event_id: "staff-image", from_role: "support", attachments: [{artifact_id: "staff-image", name: "Решение.jpg", url: "/api/artifacts/staff-image/download"}]},
  ]} events={[]} />);
  expect(screen.getByRole("img", {name: "Миниатюра: Моя ошибка.png"})).toHaveAttribute("src", "/api/artifacts/owner-image/download");
  fireEvent.click(screen.getByRole("button", {name: "Открыть изображение Решение.jpg"}));
  const dialog = screen.getByRole("dialog", {name: "Просмотр изображения: Решение.jpg"});
  expect(dialog).toBeVisible();
  expect(screen.getByRole("link", {name: "Скачать Решение.jpg"})).toHaveAttribute("download");
  fireEvent.click(screen.getByRole("button", {name: "Закрыть просмотр изображения"}));
  fireEvent(dialog, new Event("close"));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("retains ordinary file downloads and never embeds an external image", () => {
  render(<RequesterConversation messages={[{event_id: "files", attachments: [
    {artifact_id: "doc", name: "Инструкция.pdf", mime_type: "application/pdf"},
    {artifact_id: "external", name: "Внешняя.png", url: "https://foreign.test/image.png"},
  ]}]} events={[]} />);
  expect(screen.getByRole("link", {name: "Инструкция.pdf"})).toHaveAttribute("href", "/api/artifacts/doc/download");
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});
it("shows public progress and system notices once, and labels admin replies as support", () => {
  render(<RequesterConversation messages={[
    { event_id: "1", from_role: "admin", text: "Здравствуйте", ts: "2026-11-05T08:00:00Z" },
    { event_id: "2", from_role: "user", text: "Код доступа к обращению сформирован.", metadata: { message_kind: "ticket_access_notice" }, ts: "2026-11-05T08:01:00Z" },
  ]} events={[
    { id: "1", type: "chat_message", requester_timeline_kind: "support_message", requester_timeline_text: "Здравствуйте" },
    { id: "3", type: "status_changed", requester_timeline_kind: "system_event", requester_timeline_text: "Специалист взял обращение в работу.", ts: "2026-11-05T08:02:00Z" },
  ]} />);
  expect(screen.getAllByText("Здравствуйте")).toHaveLength(1);
  expect(screen.getByText("Поддержка")).toBeVisible();
  expect(screen.getByText("Специалист взял обращение в работу.")).toBeVisible();
  expect(screen.getByText("Код доступа к обращению сформирован.")).toBeVisible();
  expect(screen.queryByText("Заявитель")).not.toBeInTheDocument();
});
