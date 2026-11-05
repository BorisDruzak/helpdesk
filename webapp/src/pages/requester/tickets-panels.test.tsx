import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createRef } from "react";
import { TicketReplyComposer, TicketResolutionPanel } from "./tickets-panels";

it("groups draft images and files with the reply and lets the requester remove one", () => {
  const remove = vi.fn();
  render(<TicketReplyComposer attachmentInputRef={createRef<HTMLInputElement>()} attachmentUploading={false} canAttachFiles handleAttachmentUpload={vi.fn()} handleSendMessage={vi.fn()} messageSending={false} messageText="Описание проблемы" setMessageText={vi.fn()} removePendingAttachment={remove} pendingAttachments={[
    {artifact_id: "shot", name: "Ошибка.png", url: "/api/artifacts/shot/download"},
    {artifact_id: "log", name: "Журнал.txt", url: "/api/artifacts/log/download"},
  ]} />);
  expect(screen.getByRole("region", {name: "Вложения к сообщению"})).toBeVisible();
  expect(screen.getByRole("button", {name: "Открыть изображение Ошибка.png"})).toBeVisible();
  fireEvent.click(screen.getByRole("button", {name: "Убрать вложение Журнал.txt"}));
  expect(remove).toHaveBeenCalledWith("log");
  expect(screen.getByRole("textbox", {name: "Ответ заявителя"})).toHaveValue("Описание проблемы");
});

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
    expect(screen.queryByRole("textbox", { name: "Комментарий для возврата в работу" })).not.toBeInTheDocument();
    const reveal = screen.getByRole("button", { name: "Проблема не решена" });
    expect(reveal).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(reveal);
    expect(reveal).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: "Вернуть в работу" }));
    expect(props.reopenTicket).toHaveBeenCalledOnce();
    expect(screen.getByRole("textbox", { name: "Комментарий для возврата в работу" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Подтвердить решение" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить оценку" })).not.toBeInTheDocument();
  });
  it("keeps optional rating and reopening collapsed while required confirmation stays visible", () => {
    const props = { ...panelProps(), canClose: true, canRate: true, canReopen: true };
    render(<TicketResolutionPanel {...props} />);
    expect(screen.getByRole("button", { name: "Подтвердить решение" })).toBeVisible();
    expect(screen.getByText("Проверьте результат. Обращение закроется после вашего подтверждения.")).toBeVisible();
    expect(screen.queryByRole("spinbutton", { name: "Оценка обращения" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Отправить оценку" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Вернуть в работу" })).not.toBeInTheDocument();
    const reveal = screen.getByRole("button", { name: "Оценить решение" });
    fireEvent.click(reveal);
    expect(reveal).toHaveAttribute("aria-expanded", "true");
    fireEvent.change(screen.getByRole("spinbutton", { name: "Оценка обращения" }), { target: { value: "4" } });
    expect(props.setFeedbackRating).toHaveBeenCalledWith(4);
    fireEvent.click(screen.getByRole("button", { name: "Отправить оценку" }));
    expect(props.submitFeedback).toHaveBeenCalledOnce();
    expect(screen.queryByRole("textbox", { name: "Комментарий для возврата в работу" })).not.toBeInTheDocument();
    fireEvent.click(reveal);
    expect(screen.queryByRole("spinbutton", { name: "Оценка обращения" })).not.toBeInTheDocument();
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
