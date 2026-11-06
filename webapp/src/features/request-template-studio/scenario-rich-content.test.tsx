import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { ScenarioRichContent, canonicalRichDocument } from "./scenario-rich-content";
import { ScenarioStepContent } from "../requester/scenario-step-content";
it("shows formatted question help once while retaining the fallback for old clients", () => {
  render(<ScenarioStepContent block={{ id: "q", kind: "form_page", title: "Вопрос", fields: [{ key: "a", type: "text", label: "Описание", help_text: "Пояснение", help_document: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Пояснение" }] }] } }] }} values={{}} acknowledged={false} onValue={() => {}} onAcknowledged={() => {}} />);
  expect(screen.getAllByText("Пояснение")).toHaveLength(1);
});
it("renders safe formatted content and scoped screenshots without executing arbitrary nodes or links", () => {
  const asset = { asset_id: "a", name: "shot.png", mime_type: "image/png", size_bytes: 10, url: "/api/web/request-scenario-assets/a/download" };
  render(<ScenarioRichContent document={{ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Важный текст", marks: [{ type: "bold" }] }, { type: "text", text: "Опасная ссылка", marks: [{ type: "link", attrs: { href: "javascript:alert(1)" } }] }] }, { type: "image", attrs: { asset_id: "a", alt: "Пример ошибки" } }, { type: "image", attrs: { asset_id: "unknown" } }, { type: "script", text: "secret" }] }} attachments={[asset]} />);
  expect(screen.getByText("Важный текст").tagName).toBe("STRONG");
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Пример ошибки" })).toHaveAttribute("src", asset.url);
  expect(screen.getAllByRole("img")).toHaveLength(1);
  expect(document.querySelector("script")).toBeNull();
});
it("normalizes editor defaults and never serializes HTML attributes", () => {
  expect(canonicalRichDocument({ type: "doc", content: [{ type: "paragraph", attrs: { onclick: "x" }, content: [{ type: "text", text: "Ссылка", marks: [{ type: "link", attrs: { href: "https://example.org", target: "_blank", rel: "noopener" } }] }] }] })).toEqual({ type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Ссылка", marks: [{ type: "link", attrs: { href: "https://example.org" } }] }] }] });
});
