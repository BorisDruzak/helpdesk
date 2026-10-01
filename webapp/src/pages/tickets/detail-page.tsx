import { useTicketDetailController } from "./hooks/use-ticket-detail-controller";
import { TicketDetailWorkspace } from "./detail-workspace";
export { TicketRequestFormCard } from "./sections/TicketRequestFormCard";
export { TicketWorkVisibilityCard } from "./sections/TicketWorkVisibilityCard";
export { TicketStatusActionPanel } from "./sections/TicketStatusActionPanel";
export { TicketApprovalsPanel } from "./sections/TicketApprovalsPanel";
export { TicketOnBehalfContextCard } from "./sections/TicketOnBehalfContextCard";
export { TicketAutomationPanel } from "./sections/TicketAutomationPanel";
export { TicketPassportPanel } from "./sections/TicketPassportPanel";
export { PASSPORT_SECTION_LABELS } from "./detail-formatting";

export function TicketDetailPage() {
  const controller = useTicketDetailController();
  return <TicketDetailWorkspace controller={controller} />;
}
