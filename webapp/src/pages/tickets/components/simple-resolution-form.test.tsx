import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SimpleResolutionForm } from "./simple-resolution-form";

describe("simple resolution form", () => {
  it("requires a public result for ordinary resolve and close without a manual code", () => {
    const save = vi.fn();
    render(<SimpleResolutionForm closeAfterResolve requirements={[]} pending={false} onSubmit={save} onCancel={vi.fn()} onAdvanced={vi.fn()} />);
    expect(screen.queryByLabelText("Код решения")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Решить и закрыть" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Итог для сотрудника"), { target: { value: "Принтер проверен" } });
    fireEvent.click(screen.getByRole("button", { name: "Решить и закрыть" }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ requesterResolutionSummary: "Принтер проверен" }));
  });

  it.each(["resolution_code", "allowed_resolution_code"])("ignores obsolete %s requirements without manual entry", (key) => {
    const save = vi.fn();
    render(<SimpleResolutionForm requirements={[{ key, label: "Специальный код решения", met: false, detail: "Устаревшее требование" }]} pending={false} onSubmit={save} onCancel={vi.fn()} onAdvanced={vi.fn()} />);
    expect(screen.queryByRole("textbox", { name: /Код решения/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Специальный код решения" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Итог для сотрудника"), { target: { value: "Принтер проверен" } });
    fireEvent.click(screen.getByRole("button", { name: "Решить обращение" }));
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ requesterResolutionSummary: "Принтер проверен", resolutionCode: "" }));
  });
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
