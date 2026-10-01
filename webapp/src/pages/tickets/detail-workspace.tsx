import {
  TicketQueueSidebar,
} from "./sections/TicketQueueSidebar";
import {
  TicketConversationWorkspace,
} from "./sections/TicketConversationWorkspace";
import {
  TicketInfoSidebar,
} from "./sections/TicketInfoSidebar";
import {
  TicketDeviceSidebar,
} from "./sections/TicketDeviceSidebar";
import {
  TicketToolsSidebar,
} from "./sections/TicketToolsSidebar";
import {
  TicketOperationalOverview,
} from "./sections/TicketOperationalOverview";
import {
  ArrowLeft,
  Copy,
  RefreshCcw,
} from "lucide-react";
import {
  Navigate,
} from "react-router-dom";
import {
  Badge,
} from "../../components/ui/badge";
import {
  Button,
} from "../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../components/ui/card";
import {
  getTicketStatusTone,
} from "../../features/tickets/status-presentation";
import {
  formatDateTime,
} from './detail-formatting';
import {
  TicketWorkVisibilityCard,
} from './sections/TicketWorkVisibilityCard';
import {
  TicketStatusActionPanel,
} from './sections/TicketStatusActionPanel';
import {
  TicketApprovalsPanel,
} from './sections/TicketApprovalsPanel';
import {
  TicketOnBehalfContextCard,
} from './sections/TicketOnBehalfContextCard';
import {
  TicketAutomationPanel,
} from './sections/TicketAutomationPanel';
import {
  useTicketDetailController,
} from "./hooks/use-ticket-detail-controller";
export function TicketDetailWorkspace({ controller }: { controller: ReturnType<typeof useTicketDetailController> }) {
  const { navigate, ticketId, statusAction, setStatusAction, selectedPlaybookVersionId, setSelectedPlaybookVersionId, queueQuery, detailQuery, toolsQuery, playbooksQuery, passportQuery, passportCandidatesQuery, playbooks, statusMutation, playbookMutation, queue, detail, autoPlaybookEvents, statusAccess, playbookAccess, latestOperations } = controller;
  if (!ticketId) {
    return <Navigate replace to="/app/tickets" />;
  }
  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              leadingIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate("/app/tickets")}
              size="sm"
              variant="outline"
            >
              Назад
            </Button>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-semibold tracking-tight text-slate-950 md:text-3xl">
                Тикет #{detail?.ticket.ticket_code ?? ticketId}
              </h1>
              <button
                className="rounded-full border border-border p-2 text-slate-400 transition-colors hover:text-brand-700"
                onClick={async () => {
                  await navigator.clipboard.writeText(detail?.ticket.ticket_code ?? ticketId);
                }}
                type="button"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div>
            <p className="text-2xl font-semibold tracking-tight text-slate-950">
              {detail?.ticket.title ?? "Загружаем карточку тикета..."}
            </p>
            <p className="mt-2 text-sm text-slate-500">
              Создан: {formatDateTime(detail?.ticket.created_at)}
              {detail?.ticket.requester_display_name ? ` • Клиент: ${detail.ticket.requester_display_name}` : ""}
              {detail?.ticket.queue.code ? ` • Очередь: ${detail.ticket.queue.code}` : ""}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-start justify-end gap-3">
          {detail ? (
            <TicketStatusActionPanel
              disabled={!detail}
              disabledReason={statusAccess.allowed ? null : statusAccess.reason}
              onApply={(value) => {
                if (!value) {
                  return;
                }
                void statusMutation.mutateAsync(value);
              }}
              onValueChange={setStatusAction}
              pending={statusMutation.isPending}
              selectedStatus={statusAction}
              statusOptions={detail.actions.status_options}
              closureRequirements={detail.actions.closure_requirements ?? []}
              ticket={detail.ticket}
            />
          ) : (
            <div className="min-w-[260px] rounded-[1.1rem] border border-border bg-white px-4 py-4 shadow-soft">
              <Badge tone={getTicketStatusTone("")} withDot>Загружаем</Badge>
            </div>
          )}
          <Button
            disabled={detailQuery.isFetching || toolsQuery.isFetching || playbooksQuery.isFetching}
            leadingIcon={<RefreshCcw className="h-4 w-4" />}
            onClick={() => {
              void Promise.all([
                detailQuery.refetch(),
                queueQuery.refetch(),
                toolsQuery.refetch(),
                playbooksQuery.refetch(),
                passportQuery.refetch(),
                passportCandidatesQuery.refetch(),
              ]);
            }}
            size="sm"
            variant="outline"
          >
            Обновить
          </Button>
        </div>
      </div>

      {detailQuery.isError ? (
        <div className="rounded-[1.1rem] border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
          {detailQuery.error instanceof Error
            ? detailQuery.error.message
            : "Не удалось открыть карточку тикета."}
        </div>
      ) : null}

      {detail ? (
        <TicketOperationalOverview controller={controller} />
      ) : null}

      {detail?.ticket.approval_summary || detail?.actions.approval ? (
        <TicketApprovalsPanel
          action={detail.actions.approval}
          summary={detail.ticket.approval_summary}
        />
      ) : null}

      <div className="grid min-w-0 gap-6 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
        <TicketQueueSidebar controller={controller} />

        <TicketConversationWorkspace controller={controller} />

        <div className="min-w-0 space-y-4 xl:sticky xl:top-[8.5rem] xl:max-h-[calc(100vh-10rem)] xl:self-start xl:overflow-y-auto xl:pr-1">
          {detail ? <TicketWorkVisibilityCard ticket={detail.ticket} /> : null}

          <TicketInfoSidebar controller={controller} />

          {detail ? (
            <TicketOnBehalfContextCard
              diagnosticTarget={playbooksQuery.data?.diagnostic_target ?? toolsQuery.data?.diagnostic_target ?? null}
              ticket={detail.ticket}
            />
          ) : null}

          {detail?.request_form ? (
            <Card>
              <CardHeader>
                <CardTitle>Данные формы</CardTitle>
                <CardDescription>
                  {detail.request_form.form_title ?? detail.request_form.form_key ?? "структурированный ввод"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">request_kind</p>
                    <p className="mt-2 font-semibold text-slate-950">
                      {detail.request_form.request_kind ?? "не указан"}
                    </p>
                  </div>
                  <div className="rounded-[1rem] bg-surface-subtle px-4 py-3">
                    <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Форма</p>
                    <p className="mt-2 font-semibold text-slate-950">
                      {detail.request_form.form_key ?? "не указана"}
                    </p>
                  </div>
                </div>

                {detail.request_form.rows.length > 0 ? (
                  <dl className="space-y-3">
                    {detail.request_form.rows.map((row) => (
                      <div
                        className="flex items-start justify-between gap-3 rounded-[1rem] border border-slate-200/80 px-4 py-3"
                        key={`${row.key}-${row.label}`}
                      >
                        <dt className="text-slate-500">{row.label}</dt>
                        <dd className="max-w-[60%] text-right font-medium text-slate-900">{row.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="text-slate-500">Структурированные ответы пока не заполнены.</p>
                )}
              </CardContent>
            </Card>
          ) : null}

          <TicketDeviceSidebar controller={controller} />

          <TicketAutomationPanel
            autoPlaybookEvents={autoPlaybookEvents}
            diagnosticDeviceId={playbooksQuery.data?.device_id ?? toolsQuery.data?.device_id ?? null}
            diagnosticPolicy={playbooksQuery.data?.diagnostic_policy ?? null}
            diagnosticTarget={playbooksQuery.data?.diagnostic_target ?? toolsQuery.data?.diagnostic_target ?? null}
            disabledReason={playbookAccess.allowed ? null : playbookAccess.reason}
            latestOperations={latestOperations}
            onRunPlaybook={(playbookVersionId) => {
              void playbookMutation.mutateAsync(playbookVersionId);
            }}
            playbookErrorMessage={
              playbookMutation.isError
                ? playbookMutation.error instanceof Error
                  ? playbookMutation.error.message
                  : "Не удалось запустить плейбук."
                : null
            }
            playbookPending={playbookMutation.isPending}
            playbookResultMessage={playbookMutation.isSuccess ? playbookMutation.data.message : null}
            playbooks={playbooks}
            playbooksErrorMessage={
              playbooksQuery.isError
                ? playbooksQuery.error instanceof Error
                  ? playbooksQuery.error.message
                  : "Не удалось загрузить плейбуки."
                : null
            }
            playbooksLoading={playbooksQuery.isLoading}
            recentRuns={playbooksQuery.data?.recent_runs ?? []}
            selectedPlaybookVersionId={selectedPlaybookVersionId}
            setSelectedPlaybookVersionId={setSelectedPlaybookVersionId}
          />

          <TicketToolsSidebar controller={controller} />
        </div>
      </div>
    </section>
  );
}