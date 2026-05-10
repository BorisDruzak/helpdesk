import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RemoteAssistViewer, extractClipboardFiles } from "./remote-assist-viewer";
import { endRemoteAssistSession, failRemoteAssistSession, fetchRemoteAssistViewer, requestRemoteAssist } from "./api";

vi.mock("./api", () => ({
  endRemoteAssistSession: vi.fn(),
  failRemoteAssistSession: vi.fn(),
  fetchRemoteAssistViewer: vi.fn(),
  requestRemoteAssist: vi.fn(),
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
  it("extracts files pasted by browsers that expose clipboard items instead of clipboard files", () => {
    const file = new File(["content"], "report.txt", { type: "text/plain", lastModified: 10 });
    const data = {
      files: [],
      items: [
        { kind: "string", getAsFile: () => null },
        { kind: "file", getAsFile: () => file },
      ],
    } as unknown as DataTransfer;

    expect(extractClipboardFiles(data)).toEqual([file]);
  });

  it("returns to the ticket when the operator ends a session", async () => {
    vi.mocked(fetchRemoteAssistViewer).mockResolvedValue(viewerInfo);
    vi.mocked(endRemoteAssistSession).mockResolvedValue(viewerInfo);
    vi.mocked(failRemoteAssistSession).mockResolvedValue(viewerInfo);
    const onClose = vi.fn();
    const onEnded = vi.fn();

    render(<RemoteAssistViewer onClose={onClose} onEnded={onEnded} sessionId="session-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Завершить" }));

    await waitFor(() => expect(endRemoteAssistSession).toHaveBeenCalledWith("session-1"));
    expect(onEnded).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("requests elevated admin from the viewer after ending the current session", async () => {
    vi.mocked(fetchRemoteAssistViewer).mockResolvedValue({
      ...viewerInfo,
      mode: "interactive_control",
      status: "active",
      token: "",
      features: { clipboard_auto_sync: true, file_transfer: true },
    });
    vi.mocked(endRemoteAssistSession).mockResolvedValue(viewerInfo);
    vi.mocked(failRemoteAssistSession).mockResolvedValue(viewerInfo);
    vi.mocked(requestRemoteAssist).mockResolvedValue({
      session_id: "elevated-session",
      status: "waiting_consent",
      expires_at: "2026-05-10T00:00:00Z",
      message: "ok",
    });
    const onClose = vi.fn();
    const onEnded = vi.fn();

    render(
      <RemoteAssistViewer
        canRequestElevated
        onClose={onClose}
        onEnded={onEnded}
        onElevatedRequested={vi.fn()}
        sessionId="session-1"
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Повысить права" }));

    await waitFor(() => expect(endRemoteAssistSession).toHaveBeenCalledWith("session-1", "elevated_requested"));
    expect(requestRemoteAssist).toHaveBeenCalledWith("ticket-1", expect.objectContaining({
      deviceId: "device-1",
      mode: "elevated_admin",
      features: { clipboard_auto_sync: true, file_transfer: true },
    }));
    expect(onEnded).toHaveBeenCalledTimes(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
