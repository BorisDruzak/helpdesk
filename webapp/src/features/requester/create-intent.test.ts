import { afterEach, describe, expect, it, vi } from "vitest";
import { pendingCreateKey, clearCreateKey } from "./create-intent";

afterEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("pending requester creation", () => {
  it("keeps the key across retry and a refreshed caller", () => {
    const first = pendingCreateKey("actor-a", "");
    expect(pendingCreateKey("actor-a", "")).toBe(first);
  });
  it("separates accounts and explicitly different intents", () => {
    const first = pendingCreateKey("actor-a", "");
    expect(pendingCreateKey("actor-b", "")).not.toBe(first);
    expect(pendingCreateKey("actor-a", "another")).not.toBe(first);
  });
  it("starts a fresh request after acknowledgement", () => {
    const first = pendingCreateKey("actor-a", "");
    clearCreateKey("actor-a", "");
    expect(pendingCreateKey("actor-a", "")).not.toBe(first);
  });
  it("does not start an untracked submission when storage fails", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    expect(() => pendingCreateKey("actor-a", "")).toThrow();
  });
  it("does not accept an anonymous account namespace", () => {
    expect(() => pendingCreateKey("", "")).toThrow();
  });
});
