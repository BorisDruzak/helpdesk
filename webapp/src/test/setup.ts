import "@testing-library/jest-dom/vitest";

// React Flow observes canvas and node dimensions; JSDOM has no layout engine.
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
// React Flow reads CSS transform scale while refreshing dynamic handles. JSDOM
// renders no geometry; actual transform/port behavior is covered in Chromium.
Object.defineProperty(globalThis, "DOMMatrixReadOnly", { configurable: true, value: class DOMMatrixReadOnly { m22 = 1; } });
// Modal focus trapping is exercised in Chromium; JSDOM has no showModal API.
HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
HTMLDialogElement.prototype.close = function () { this.removeAttribute("open"); };
