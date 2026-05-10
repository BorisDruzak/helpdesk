import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RemoteAssistViewer } from "./remote-assist-viewer";
import { endRemoteAssistSession, fetchRemoteAssistViewer } from "./api";

vi.mock("./api", () => ({
  endRemoteAssistSession: vi.fn(),
  fetchRemoteAssistViewer: vi.fn(),
}));

const viewerInfo = {
  session_id: "session-1",
  ticket_id: "ticket-1",
  device_id: "device-1",
  operator_id: "operator-1",
  mode: "view_only",
  status: "ended",
  reason: null,
  consent_status: "approved",
  requested_at: null,
  approved_at: null,
  denied_at: null,
  started_at: null,
  ended_at: null,
  expires_at: null,
  max_duration_sec: 900,
  close_reason: null,
  error_code: null,
  error_message: null,
  signaling_url: "/ws/remote-assist/session-1",
  token: "",
  ice_servers: [],
};

describe("RemoteAssistViewer", () => {
  it("returns to the ticket when the operator ends a session", async () => {
    vi.mocked(fetchRemoteAssistViewer).mockResolvedValue(viewerInfo);
    vi.mocked(endRemoteAssistSession).mockResolvedValue(viewerInfo);
    const onClose = vi.fn();
    const onEnded = vi.fn();

    render(<RemoteAssistViewer onClose={onClose} onEnded={onEnded} sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Завершить" }));

    await waitFor(() => expect(endRemoteAssistSession).toHaveBeenCalledWith("session-1"));
    expect(onEnded).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
