import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { cleanup, fireEvent, render as renderView, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioWizard } from "./scenario-wizard";
function render(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderView(ui, { wrapper: ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> });
}
vi.mock("./scenario-map-workbench", () => ({ ScenarioMapWorkbench: ({ onCheck, issueBlockId, onPublicationRules }: any) => {
  const [value, setValue] = useState("");
  return <section aria-label="Карта"><input aria-label="Положение карты" value={value} onChange={event => setValue(event.target.value)} /><button onClick={onCheck}>Проверить из карты</button><button onClick={() => onPublicationRules(["visibility"])}>Правила услуги</button><output>{issueBlockId}</output></section>;
} }));
vi.mock("./scenario-publication-settings", () => ({ ScenarioPublicationSettings: ({ requestId, focusPolicy }: any) => <section aria-label="Обработка услуги"><output>{focusPolicy}:{requestId}</output></section> }));
vi.mock("./scenario-publication", () => ({ ScenarioPublication: ({ onBack, onIssue, settingsPanel }: any) => <section aria-label="Публикация сценария"><h1>Публикация сценария</h1>{settingsPanel}<button onClick={onBack}>Вернуться к карте</button><button onClick={() => onIssue({ step: 1, blockId: "submit", label: "Завершение" })}>Исправить завершение</button><button onClick={() => onIssue({ step: 2, policy: "sla", label: "Сроки" })}>Исправить сроки</button></section> }));
vi.mock("./scenario-author-attachments", () => ({ ScenarioAuthorAttachmentProvider: ({ children }: any) => children }));
afterEach(cleanup);
const props: any = { definition: { scenario_key: "s", blocks: [], process_binding: {} }, detail: { scenario: { id: "s" }, draft: { revision: 1 } }, catalog: { offerings: [] }, dirty: false, disabled: false, onChange: vi.fn() };
it("opens publication as a separate page while keeping the map mounted with its local context", () => {
  render(<ScenarioWizard {...props} />);
  fireEvent.change(screen.getByRole("textbox", { name: "Положение карты" }), { target: { value: "выбранный блок" } });
  fireEvent.click(screen.getByRole("button", { name: "Опубликовать" }));
  expect(screen.getByRole("heading", { name: "Публикация сценария" })).toBeVisible();
  expect(screen.queryByRole("region", { name: "Карта" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("Положение карты")).toHaveValue("выбранный блок");
  fireEvent.click(screen.getByRole("button", { name: "Вернуться к карте" }));
  expect(screen.getByRole("region", { name: "Карта" })).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Положение карты" })).toHaveValue("выбранный блок");
});
it("opens the same full page from map checks and returns to the issue block", () => {
  render(<ScenarioWizard {...props} />);
  fireEvent.click(screen.getByRole("button", { name: "Проверить из карты" }));
  expect(screen.getByRole("region", { name: "Публикация сценария" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Исправить завершение" }));
  expect(screen.getByRole("region", { name: "Карта" })).toBeVisible();
  expect(screen.getByText("submit")).toBeVisible();
});
it("keeps service-wide remediation on publication and reopens the same setting repeatedly", () => {
 render(<ScenarioWizard {...props} />);
 fireEvent.click(screen.getByRole("button", { name: "Правила услуги" }));
 expect(screen.getByRole("region", { name: "Публикация сценария" })).toBeVisible();
 expect(screen.getByText("visibility:1")).toBeVisible();
 fireEvent.click(screen.getByRole("button", { name: "Исправить сроки" }));
 expect(screen.getByText("sla:2")).toBeVisible();
 fireEvent.click(screen.getByRole("button", { name: "Исправить сроки" }));
 expect(screen.getByText("sla:3")).toBeVisible();
 expect(screen.queryByRole("region", { name: "Карта" })).not.toBeInTheDocument();
});
