import {
  TicketDialogTab,
} from "./TicketDialogTab";
import {
  TicketInfoTab,
} from "./TicketInfoTab";
import {
  TicketHistoryTab,
} from "./TicketHistoryTab";
import {
  TicketDialogTabComposer,
} from "./TicketDialogTabComposer";
import {
  Card,
  CardContent,
} from "../../../components/ui/card";
import {
  Tabs,
} from "../../../components/ui/tabs";
import {
  DiagnosticCenterPanel,
} from "../../../features/diagnostics/diagnostic-center-panel";
import {
  ArtifactPreview,
} from './ArtifactPreview';
import {
  TicketPassportPanel,
} from './TicketPassportPanel';
import {
  useTicketDetailController,
} from "../hooks/use-ticket-detail-controller";
export function TicketConversationWorkspace({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { navigate, ticketId, activeTab, setActiveTab, detailQuery, passportQuery, passportCandidatesQuery, passportGenerateMutation, passportLinkCandidateMutation, passportCreateEvidenceMutation, passportPatchSectionsMutation, detail, passport, attachments, passportAccess, tabItems } = controller;
  if (!ticketId) return null;
  return (<Card className="w-full overflow-hidden">
    <CardContent className="flex h-[min(72vh,62rem)] min-h-[34rem] flex-col px-0 pb-0 pt-0">
      <div className="border-b border-border px-6 py-5">
        <Tabs items={tabItems} onValueChange={setActiveTab} value={activeTab} />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        {detailQuery.isLoading ? (
          <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
            Загружаем карточку тикета...
          </div>
        ) : null}

        {<TicketDialogTab controller={controller} />}

        {detail && activeTab === "diagnostics" ? <DiagnosticCenterPanel ticketId={ticketId} /> : null}

        {<TicketInfoTab controller={controller} />}

        {detail && activeTab === "files" ? (
          <div className="space-y-3">
            {attachments.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                {attachments.map((attachment) => (
                  <ArtifactPreview key={attachment.id} attachment={attachment} />
                ))}
              </div>
            ) : (
              <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
                В реальной ленте пока нет вложений или артефактов.
              </div>
            )}
          </div>
        ) : null}

        {<TicketHistoryTab controller={controller} />}

        {activeTab === "passport" ? (
          passportQuery.isLoading ? (
            <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center text-sm text-slate-500">
              Загружаем паспорт решения...
            </div>
          ) : passportQuery.isError ? (
            <div className="rounded-[1.1rem] border border-rose-200 bg-rose-50 px-5 py-5 text-sm text-rose-700">
              {passportQuery.error instanceof Error
                ? passportQuery.error.message
                : "Не удалось загрузить паспорт решения."}
            </div>
          ) : (
            <TicketPassportPanel
              candidates={passportCandidatesQuery.data}
              disabledReason={passportAccess.allowed ? null : passportAccess.reason}
              isCreatingEvidence={passportCreateEvidenceMutation.isPending}
              isGenerating={passportGenerateMutation.isPending}
              isLinkingCandidate={passportLinkCandidateMutation.isPending}
              isPatchingSections={passportPatchSectionsMutation.isPending}
              onCreateEvidence={(evidence) => passportCreateEvidenceMutation.mutate(evidence)}
              onGenerate={() => passportGenerateMutation.mutate("create")}
              onLinkCandidate={(link) => passportLinkCandidateMutation.mutate(link)}
              onPatchSections={(patch) => passportPatchSectionsMutation.mutate(patch)}
              onPrint={() => navigate(`/app/tickets/${ticketId}/passport/print`)}
              onRefresh={() => passportGenerateMutation.mutate("refresh")}
              payload={passport}
            />
          )
        ) : null}
      </div>

      {<TicketDialogTabComposer controller={controller} />}
    </CardContent>
  </Card>);
}