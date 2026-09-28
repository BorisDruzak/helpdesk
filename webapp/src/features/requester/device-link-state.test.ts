import { afterEach, describe, expect, it, vi } from "vitest";
import { captureDeviceLinkFragment, clearPendingDeviceCode, pendingDeviceCode } from "./device-link-state";

afterEach(() => { clearPendingDeviceCode(); vi.useRealTimers(); });

describe("temporary possession code", () => {
  it("captures and removes the fragment before auth navigation without durable storage", () => {
    window.history.replaceState({}, "", "/app/requester/devices/link#code=123456");
    const local = vi.spyOn(Storage.prototype, "setItem");
    captureDeviceLinkFragment();
    expect(window.location.hash).toBe("");
    expect(pendingDeviceCode()).toBe("123456");
    window.history.replaceState({}, "", "/app/login?next=%2Fapp%2Frequester%2Fdevices%2Flink");
    expect(pendingDeviceCode()).toBe("123456");
    expect(local).not.toHaveBeenCalled();
    local.mockRestore();
  });
  it("expires from memory and never captures retired query pairing", () => {
    vi.useFakeTimers();
    window.history.replaceState({}, "", "/app/requester/devices/link#code=123456");
    captureDeviceLinkFragment();
    vi.advanceTimersByTime(600_001);
    expect(pendingDeviceCode()).toBe("");
    window.history.replaceState({}, "", "/app/register?pairing_code=123456");
    captureDeviceLinkFragment();
    expect(pendingDeviceCode()).toBe("");
  });
});
