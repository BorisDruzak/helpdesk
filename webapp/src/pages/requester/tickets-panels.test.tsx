import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TicketResolutionPanel } from "./tickets-panels";

function panelProps() {
  return { actionSubmitting: false, canClose: false, canRate: false, canReopen: false,
    closeTicket: vi.fn(), submitFeedback: vi.fn(), reopenTicket: vi.fn(),
    feedbackComment: "", feedbackProblemResolved: true, feedbackRating: 5, feedbackReason: "not_resolved",
    reopenComment: "", reopenReason: "problem_returned", setFeedbackComment: vi.fn(),
    setFeedbackProblemResolved: vi.fn(), setFeedbackRating: vi.fn(), setFeedbackReason: vi.fn(),
    setReopenComment: vi.fn(), setReopenReason: vi.fn() };
}

describe("requester result actions", () => {
  it("shows reopen independently of rating and confirmation", () => {
    const props = { ...panelProps(), canReopen: true };
    render(<TicketResolutionPanel {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Вернуть в работу" }));
    expect(props.reopenTicket).toHaveBeenCalledOnce();
    expect(screen.getByRole("textbox", { name: "Комментарий для возврата в работу" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Подтвердить решение" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить оценку" })).not.toBeInTheDocument();
  });
  it("shows only granted confirmation or rating actions", () => {
    render(<TicketResolutionPanel {...panelProps()} canClose />);
    expect(screen.getByRole("button", { name: "Подтвердить решение" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Вернуть в работу" })).not.toBeInTheDocument();
    expect(screen.queryByRole("spinbutton", { name: "Оценка обращения" })).not.toBeInTheDocument();
  });
  it("renders no action panel without granted capabilities", () => {
    const { container } = render(<TicketResolutionPanel {...panelProps()} />);
    expect(container).toBeEmptyDOMElement();
  });
});
