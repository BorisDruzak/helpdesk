import {
  Badge,
} from "../../../components/ui/badge";
import {
  Button,
} from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import {
  Select,
} from "../../../components/ui/select";
import {
  type SupportTicketDetailPayload,
  type SupportTicketPlaybooksPayload,
} from "../../../features/queues/api";
import {
  getTicketStatusTone,
} from "../../../features/tickets/status-presentation";
import {
  formatDateTime,
  getOperationTitle,
  getOperationScopeLabel,
  getOperationDisplayStatus,
  getOperationDisplayLabel,
  TicketAutomationPlaybook,
  TicketDiagnosticPolicy,
  TicketDiagnosticTarget,
  formatDiagnosticPolicyList,
  formatDiagnosticTarget,
  diagnosticPolicyBadges,
} from '../detail-formatting';
export function TicketAutomationPanel({
  autoPlaybookEvents,
  diagnosticDeviceId = null,
  diagnosticPolicy = null,
  diagnosticTarget = null,
  disabledReason = null,
  latestOperations,
  onRunPlaybook,
  playbookErrorMessage,
  playbookPending,
  playbookResultMessage,
  playbooks,
  playbooksErrorMessage,
  playbooksLoading,
  recentRuns,
  selectedPlaybookVersionId,
  setSelectedPlaybookVersionId,
}: {
  autoPlaybookEvents: SupportTicketDetailPayload["timeline"];
  diagnosticDeviceId?: string | null;
  diagnosticPolicy?: TicketDiagnosticPolicy | null;
  diagnosticTarget?: TicketDiagnosticTarget | null;
  disabledReason?: string | null;
  latestOperations: SupportTicketDetailPayload["snapshot"]["latest_operations"];
  onRunPlaybook: (playbookVersionId: number) => void;
  playbookErrorMessage: string | null;
  playbookPending: boolean;
  playbookResultMessage: string | null;
  playbooks: TicketAutomationPlaybook[];
  playbooksErrorMessage: string | null;
  playbooksLoading: boolean;
  recentRuns: NonNullable<SupportTicketPlaybooksPayload["recent_runs"]>;
  selectedPlaybookVersionId: number | null;
  setSelectedPlaybookVersionId: (playbookVersionId: number | null) => void;
}) {
  const selectedPlaybook = playbooks.find((item) => item.playbook_version_id === selectedPlaybookVersionId) ?? null;
  const latestAutoPlaybook = autoPlaybookEvents[0] ?? null;
  const launchDisabled = Boolean(disabledReason) || playbookPending || !selectedPlaybook || !selectedPlaybook.can_run;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Автоматизация</CardTitle>
        <CardDescription>
          Единая точка запуска диагностических плейбуков из тикета: выбор, preflight-readiness и контроль последних операций.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Плейбук</p>
            <p className="mt-2 font-semibold text-slate-950">
              {selectedPlaybook?.name ?? "Выберите опубликованный сценарий"}
            </p>
          </div>
          <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Preflight</p>
            <p className="mt-2 font-semibold text-slate-950">
              {selectedPlaybook?.readiness_label ?? "Ожидаем выбор"}
            </p>
          </div>
        </div>

        {playbooksLoading ? <p className="text-sm text-slate-500">Загружаем опубликованные плейбуки...</p> : null}
        <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-3">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Цель диагностики</p>
          <p className="mt-2 font-semibold text-slate-950">
            {formatDiagnosticTarget(diagnosticTarget, diagnosticDeviceId)}
          </p>
          {diagnosticTarget?.source ? (
            <p className="mt-1 text-xs text-slate-500">source: {diagnosticTarget.source}</p>
          ) : null}
        </div>

        {playbooksErrorMessage ? <p className="text-sm text-rose-700">{playbooksErrorMessage}</p> : null}

        {diagnosticPolicy ? (
          <div className="rounded-[1rem] border border-emerald-100 bg-emerald-50/60 px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-slate-950">Политика диагностики</p>
                <p className="mt-1 text-sm text-slate-700">
                  {formatDiagnosticPolicyList(diagnosticPolicy.suggested_playbooks, "Рекомендованные плейбуки не заданы")}
                </p>
              </div>
              <Badge tone={diagnosticPolicy.auto_run_enabled ? "success" : "neutral"}>
                {diagnosticPolicy.auto_run_enabled ? "auto-run" : "manual"}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {diagnosticPolicyBadges(diagnosticPolicy).map((badge) => (
                <Badge key={badge} tone="neutral">
                  {badge}
                </Badge>
              ))}
            </div>
            {Object.keys(diagnosticPolicy.reroute_by_result).length ? (
              <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
                {Object.entries(diagnosticPolicy.reroute_by_result).map(([result, queue]) => (
                  <span className="rounded-pill bg-white px-3 py-1 font-medium" key={`${result}:${queue}`}>
                    {result} -&gt; {queue}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {latestAutoPlaybook ? (
          <div className="rounded-[1rem] border border-blue-100 bg-blue-50/60 px-4 py-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="font-semibold text-slate-950">Автодиагностика формы</p>
              <Badge tone="info">{latestAutoPlaybook.tool_status ?? "запущена"}</Badge>
            </div>
            <p className="mt-2 text-sm font-medium text-slate-900">{latestAutoPlaybook.text}</p>
            {latestAutoPlaybook.result_summary ? (
              <p className="mt-1 text-xs leading-5 text-slate-600">{latestAutoPlaybook.result_summary}</p>
            ) : null}
          </div>
        ) : null}

        {playbooks.length ? (
          <label className="space-y-2 text-sm font-medium text-slate-800">
            <span>Сценарий запуска</span>
            <Select
              aria-label="Сценарий запуска"
              onChange={(event) => {
                const value = Number(event.target.value);
                setSelectedPlaybookVersionId(Number.isFinite(value) && value > 0 ? value : null);
              }}
              value={selectedPlaybookVersionId ?? ""}
            >
              <option value="">Выберите плейбук</option>
              {playbooks.map((playbook) => (
                <option key={playbook.playbook_version_id} value={playbook.playbook_version_id}>
                  {playbook.name} · {playbook.version ?? playbook.key}
                </option>
              ))}
            </Select>
          </label>
        ) : !playbooksLoading ? (
          <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-5 text-sm text-slate-500">
            Опубликованных диагностических плейбуков пока нет. Создайте их в конструкторе плейбуков.
          </div>
        ) : null}

        {selectedPlaybook ? (
          <div className="rounded-[1rem] border border-border bg-white px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-slate-950">{selectedPlaybook.name}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {selectedPlaybook.key} · {selectedPlaybook.blocks_count} шагов
                </p>
              </div>
              <Badge tone={selectedPlaybook.can_run ? "success" : "warning"}>{selectedPlaybook.readiness_label}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedPlaybook.required_tools.length ? (
                selectedPlaybook.required_tools.map((tool) => (
                  <Badge key={tool} tone="neutral">
                    {tool}
                  </Badge>
                ))
              ) : (
                <span className="text-xs text-slate-500">Required tools будут проверены серверным preflight.</span>
              )}
            </div>
            {selectedPlaybook.missing_tools?.length || selectedPlaybook.missing_params?.length ? (
              <div className="mt-3 rounded-[0.9rem] border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-800">
                {selectedPlaybook.missing_tools?.length ? (
                  <p>Недоступные инструменты: {selectedPlaybook.missing_tools.join(", ")}</p>
                ) : null}
                {selectedPlaybook.missing_params?.length ? (
                  <p className="mt-1">Не заполнены обязательные параметры: {selectedPlaybook.missing_params.join(", ")}</p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        {playbookResultMessage ? <p className="text-sm text-emerald-700">{playbookResultMessage}</p> : null}
        {playbookErrorMessage ? <p className="text-sm text-rose-700">{playbookErrorMessage}</p> : null}
        {disabledReason ? (
          <p className="rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
            {disabledReason}
          </p>
        ) : null}

        <Button
          className="w-full"
          disabled={launchDisabled}
          onClick={() => {
            if (!launchDisabled && selectedPlaybook) {
              onRunPlaybook(selectedPlaybook.playbook_version_id);
            }
          }}
        >
          {playbookPending ? "Запускаем плейбук..." : "Запустить плейбук"}
        </Button>

        <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <p className="font-semibold text-slate-900">Последние плейбуки тикета</p>
            <Badge tone="neutral">{recentRuns.length}</Badge>
          </div>
          {recentRuns.length ? (
            <div className="mt-3 space-y-2">
              {recentRuns.slice(0, 3).map((run) => (
                <div className="rounded-[0.9rem] border border-border bg-white px-3 py-3" key={run.playbook_run_id}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium text-slate-900">
                        {run.playbook_name || run.playbook_key || `Run #${run.playbook_run_id}`}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Run #{run.playbook_run_id} • {run.trigger_type || "manual"} • завершён {formatDateTime(run.finished_at)}
                      </p>
                    </div>
                    <Badge tone={getTicketStatusTone(run.status)}>{run.status}</Badge>
                  </div>
                  {run.error_message || run.error_code ? (
                    <p className="mt-2 rounded-[0.75rem] border border-rose-100 bg-rose-50 px-3 py-2 text-xs font-medium text-rose-800">
                      {run.error_code ? `${run.error_code}: ` : ""}
                      {run.error_message || "Плейбук завершился ошибкой"}
                    </p>
                  ) : null}
                  {run.step_errors.length ? (
                    <div className="mt-2 space-y-1">
                      {run.step_errors.slice(0, 3).map((error) => (
                        <p
                          className="rounded-[0.75rem] border border-rose-100 bg-rose-50 px-3 py-2 text-xs text-rose-800"
                          key={`${run.playbook_run_id}:${error.step_key}:${error.tool_name}:${error.error_code}`}
                        >
                          {error.tool_name || error.step_key || "Шаг"}: {error.error_message}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Плейбуки по этому тикету ещё не запускались.</p>
          )}
        </div>

        <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
          <div className="flex items-center justify-between gap-3">
            <p className="font-semibold text-slate-900">Операции этого тикета</p>
            <Badge tone="neutral">{latestOperations.length}</Badge>
          </div>
          {latestOperations.length ? (
            <div className="mt-3 space-y-2">
              {latestOperations.slice(0, 3).map((operation) => (
                <div
                  className="flex items-start justify-between gap-3 rounded-[0.9rem] border border-border bg-white px-3 py-3"
                  key={operation.operation_id}
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-900">{getOperationTitle(operation)}</p>
                    <p className="mt-1 text-xs text-slate-500">
                      {getOperationScopeLabel(operation)} • {operation.operation_id}
                    </p>
                  </div>
                  <Badge tone={getTicketStatusTone(getOperationDisplayStatus(operation))}>
                    {getOperationDisplayLabel(operation)}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-500">Запусков по тикету пока нет.</p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}