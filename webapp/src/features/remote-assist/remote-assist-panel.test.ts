import { describe, expect, it } from "vitest";

import { buildRemoteAssistFeatureOptions } from "./remote-assist-panel";

describe("RemoteAssistPanel request options", () => {
  it("keeps clipboard auto-sync enabled for interactive control requests", () => {
    expect(buildRemoteAssistFeatureOptions("interactive_control", true, false)).toEqual({
      clipboard_auto_sync: true,
      file_transfer: false,
    });
  });

  it("keeps clipboard auto-sync enabled for elevated admin requests", () => {
    expect(buildRemoteAssistFeatureOptions("elevated_admin", true, false)).toEqual({
      clipboard_auto_sync: true,
      file_transfer: false,
    });
  });

  it("does not request clipboard auto-sync for view-only sessions", () => {
    expect(buildRemoteAssistFeatureOptions("view_only", true, false)).toEqual({
      clipboard_auto_sync: false,
      file_transfer: false,
    });
  });

  it("keeps clipboard auto-sync disabled when the permission gate clears it", () => {
    expect(buildRemoteAssistFeatureOptions("interactive_control", false, false)).toEqual({
      clipboard_auto_sync: false,
      file_transfer: false,
    });
  });

  it("allows file transfer for control sessions when requested", () => {
    expect(buildRemoteAssistFeatureOptions("interactive_control", false, true)).toEqual({
      clipboard_auto_sync: false,
      file_transfer: true,
    });
  });
});
