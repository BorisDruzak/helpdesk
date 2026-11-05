import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { RequesterConversation } from "./ticket-conversation";

afterEach(cleanup);
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
