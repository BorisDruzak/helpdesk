import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SimpleResolutionForm } from "./simple-resolution-form";

describe("simple resolution form", () => {
  it("requires only policy fields and keeps evidence reachable", () => {
    const save = vi.fn(); const advanced = vi.fn();
    render(<SimpleResolutionForm requirements={[{ key: "public_summary", label: "Итог", met: false, detail: "" }, { key: "priority_evidence", label: "Доказательство решения", met: false, detail: "Нужно доказательство" }]} pending={false} onSubmit={save} onCancel={vi.fn()} onAdvanced={advanced} />);
    expect(screen.getByRole("button", { name: "Решить обращение" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Итог для сотрудника"), { target: { value: "Принтер проверен" } });
    expect(screen.getByRole("button", { name: "Решить обращение" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Доказательство решения" }));
    expect(advanced).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Решить обращение" }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ requesterResolutionSummary: "Принтер проверен" }));
  });
});
