import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioActionBar } from "./scenario-action-bar";

afterEach(() => vi.unstubAllGlobals());
it("keeps the primary action available when its anchor is partially covered by the shell header", () => {
  let observe!: IntersectionObserverCallback;
  const disconnect = vi.fn();
  vi.stubGlobal("IntersectionObserver", class {
    constructor(callback: IntersectionObserverCallback) { observe = callback; }
    observe() {}
    disconnect = disconnect;
  });
  const view = render(<ScenarioActionBar><button>Save</button></ScenarioActionBar>);
  act(() => observe([{ isIntersecting: true, intersectionRatio: 0.3, boundingClientRect: { top: 60 } } as IntersectionObserverEntry], {} as IntersectionObserver));
  expect(screen.getByRole("button", { name: "Save" }).closest(".fixed")).not.toBeNull();
  act(() => observe([{ isIntersecting: true, intersectionRatio: 1, boundingClientRect: { top: 110 } } as IntersectionObserverEntry], {} as IntersectionObserver));
  expect(screen.getByRole("button", { name: "Save" }).closest(".fixed")).toBeNull();
  view.unmount(); expect(disconnect).toHaveBeenCalled();
});
