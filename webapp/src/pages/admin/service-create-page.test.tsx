import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { AdminServiceCreatePage } from "./service-create-page";

afterEach(() => vi.unstubAllGlobals());

it.each(["/new", "/new?service=it&category=printers&create=0"])(
  "redirects the legacy creation URL into the scenario editor (%s)", async initialEntry => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const router = createMemoryRouter([
      { path: "/new", element: <AdminServiceCreatePage /> },
      { path: "/app/admin/request-template-studio", element: <h1>Редактор услуги</h1> },
    ], { initialEntries: [initialEntry] });
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("heading", { name: "Редактор услуги" })).toBeVisible();
    expect(router.state.location.pathname).toBe("/app/admin/request-template-studio");
    const params = new URLSearchParams(router.state.location.search);
    expect(params.getAll("create")).toEqual(["1"]);
    const source = new URL(initialEntry, "https://example.test");
    expect(params.get("service")).toBe(source.searchParams.get("service"));
    expect(params.get("category")).toBe(source.searchParams.get("category"));
    expect(router.state.historyAction).toBe("REPLACE");
    expect(fetcher).not.toHaveBeenCalled();
  },
);
