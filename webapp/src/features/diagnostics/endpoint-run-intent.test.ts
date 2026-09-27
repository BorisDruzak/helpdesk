import { afterEach, describe, expect, it, vi } from "vitest";

import { clearEndpointRunKey, pendingEndpointRunKey } from "./endpoint-run-intent";

afterEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("Endpoint diagnostic intent", () => {
  it("isolates retries by actor and ticket", () => {
    const key = pendingEndpointRunKey("support-a", "ticket-a");
    expect(pendingEndpointRunKey("support-a", "ticket-a")).toBe(key);
    expect(pendingEndpointRunKey("support-b", "ticket-a")).not.toBe(key);
    expect(pendingEndpointRunKey("support-a", "ticket-b")).not.toBe(key);
  });

  it("does not clear a newer intent when an older completion arrives", () => {
    const old = pendingEndpointRunKey("support", "ticket");
    clearEndpointRunKey("support", "ticket", old);
    const next = pendingEndpointRunKey("support", "ticket");
    clearEndpointRunKey("support", "ticket", old);
    expect(pendingEndpointRunKey("support", "ticket")).toBe(next);
  });

  it("fails closed when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage disabled"); });
    expect(() => pendingEndpointRunKey("support", "ticket")).toThrow("безопасного повтора");
  });

  it("rejects a corrupted pending key without silently creating a new operation", () => {
    pendingEndpointRunKey("support", "ticket");
    sessionStorage.setItem(sessionStorage.key(0)!, "invalid key");
    expect(() => pendingEndpointRunKey("support", "ticket")).toThrow("безопасного повтора");
  });

  it.each([["", "ticket"], ["support", ""]])("requires both actor and ticket", (actor, ticket) => {
    expect(() => pendingEndpointRunKey(actor, ticket)).toThrow("безопасного повтора");
    expect(sessionStorage.length).toBe(0);
  });
});
