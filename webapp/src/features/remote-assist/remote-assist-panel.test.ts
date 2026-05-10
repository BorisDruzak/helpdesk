import { describe, expect, it } from "vitest";

import { buildRemoteAssistFeatureOptions } from "./remote-assist-panel";

describe("RemoteAssistPanel request options", () => {
  it("keeps clipboard auto-sync enabled for interactive control requests", () => {
    expect(buildRemoteAssistFeatureOptions("interactive_control", true)).toEqual({
      clipboard_auto_sync: true,
    });
  });

  it("keeps clipboard auto-sync enabled for elevated admin requests", () => {
    expect(buildRemoteAssistFeatureOptions("elevated_admin", true)).toEqual({
      clipboard_auto_sync: true,
    });
  });

  it("does not request clipboard auto-sync for view-only sessions", () => {
    expect(buildRemoteAssistFeatureOptions("view_only", true)).toEqual({
      clipboard_auto_sync: false,
    });
  });

  it("keeps clipboard auto-sync disabled when the permission gate clears it", () => {
    expect(buildRemoteAssistFeatureOptions("interactive_control", false)).toEqual({
      clipboard_auto_sync: false,
    });
  });
});
