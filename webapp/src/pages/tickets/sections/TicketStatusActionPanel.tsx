import {
  Badge,
} from "../../../components/ui/badge";
import {
  Button,
} from "../../../components/ui/button";
import {
  Select,
} from "../../../components/ui/select";
import {
  type SupportTicketDetailPayload,
} from "../../../features/queues/api";
import {
  getNextActionOwnerForStatus,
  getTicketStatusPresentation,
} from "../../../features/tickets/status-presentation";
import {
  cn,
} from "../../../shared/ui/cn";
import {
  COMMON_STATUS_TRANSITIONS,
  groupStatusOptions,
  buildTransitionOptions,
} from '../detail-formatting';
export function TicketStatusActionPanel({
  closureRequirements = [],
  disabled,
  disabledReason = null,
  onApply,
  onValueChange,
  pending,
  selectedStatus,
  statusOptions,
  ticket,
}: {
  closureRequirements?: NonNullable<SupportTicketDetailPayload["actions"]["closure_requirements"]>;
  disabled: boolean;
  disabledReason?: string | null;
  onApply: (status: string) => void;
  onValueChange: (status: string) => void;
  pending: boolean;
  selectedStatus: string;
  statusOptions: Array<{ value: string; label: string }>;
  ticket: Pick<
    SupportTicketDetailPayload["ticket"],
    | "status"
    | "status_label"
    | "requester_status_label"
    | "next_action_owner"
    | "evidence_required"
    | "evidence_ref"
  >;
}) {
  const current = getTicketStatusPresentation({
    status: ticket.status,
    statusLabel: ticket.status_label,
    requesterStatusLabel: ticket.requester_status_label,
    nextActionOwner: ticket.next_action_owner,
    evidenceRequired: ticket.evidence_required,
    evidenceRef: ticket.evidence_ref,
  });
  const selectedOption = statusOptions.find((option) => option.value === selectedStatus) ?? null;
  const selectedBlockedOption =
    selectedStatus && !selectedOption
      ? COMMON_STATUS_TRANSITIONS.find((option) => option.value === selectedStatus) ?? {
        value: selectedStatus,
        label: getTicketStatusPresentation({ status: selectedStatus }).statusLabel,
      }
      : null;
  const previewTarget = selectedOption ?? selectedBlockedOption;
  const preview = previewTarget
    ? getTicketStatusPresentation({
      status: previewTarget.value,
      statusLabel: previewTarget.label,
      requesterStatusLabel: ticket.requester_status_label,
      nextActionOwner: getNextActionOwnerForStatus(previewTarget.value),
      evidenceRequired: ticket.evidence_required,
      evidenceRef: ticket.evidence_ref,
    })
    : null;
  const evidenceBlocked =
    selectedStatus === "resolved" && Boolean(ticket.evidence_required) && !ticket.evidence_ref;
  const showClosureRequirements = selectedStatus === "resolved" && closureRequirements.length > 0;
  const transitionOptions = buildTransitionOptions(statusOptions, ticket.status);
  const transitionGroups = groupStatusOptions(transitionOptions.allowed);
  const blockedTransitionGroups = groupStatusOptions(transitionOptions.blocked);
  const actionDisabled = disabled || Boolean(disabledReason);
  const applyDisabled = actionDisabled || pending || !selectedStatus || !selectedOption;

  return (
    <div className="min-w-[320px] rounded-[1.1rem] border border-border bg-white px-4 py-4 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-700">Управление статусом</p>
          <p className="mt-1 text-sm text-slate-500">Выберите переход, проверьте guard и примените явно.</p>
        </div>
        <Badge tone={current.tone}>{current.statusLabel}</Badge>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
        <label className="space-y-2 text-sm font-medium text-slate-800">
          <span>Целевой статус</span>
          <Select
            aria-label="Целевой статус"
            disabled={actionDisabled || pending || statusOptions.length === 0}
            onChange={(event) => onValueChange(event.target.value)}
            value={selectedStatus}
          >
            <option value="">Выберите действие</option>
            {statusOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </label>
        <div className="flex items-end">
          <Button
            disabled={applyDisabled}
            onClick={() => onApply(selectedStatus)}
            size="md"
          >
            {pending ? "Применяем..." : "Применить статус"}
          </Button>
        </div>
      </div>

      {transitionGroups.length || blockedTransitionGroups.length ? (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm font-semibold text-slate-900">Быстрые переходы</p>
            <p className="text-xs text-slate-500">Выбор не меняет статус до подтверждения.</p>
          </div>
          {transitionGroups.length ? (
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">Доступно сейчас</p>
              {transitionGroups.map((group) => (
                <div key={group.label} className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{group.label}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {group.options.map((option) => {
                      const optionPresentation = getTicketStatusPresentation({
                        status: option.value,
                        statusLabel: option.label,
                        requesterStatusLabel: ticket.requester_status_label,
                        nextActionOwner: getNextActionOwnerForStatus(option.value),
                        evidenceRequired: ticket.evidence_required,
                        evidenceRef: ticket.evidence_ref,
                      });
                      const active = selectedStatus === option.value;
                      return (
                        <button
                          key={option.value}
                          className={cn(
                            "rounded-[0.9rem] border px-3 py-3 text-left transition-colors",
                            active
                              ? "border-brand-200 bg-brand-50 text-brand-900"
                              : "border-border bg-white text-slate-700 hover:border-brand-100 hover:bg-surface-subtle",
                          )}
                          disabled={actionDisabled || pending}
                          onClick={() => onValueChange(option.value)}
                          type="button"
                        >
                          <span className="block text-sm font-semibold">{option.label}</span>
                          <span className="mt-1 block text-xs text-slate-500">
                            {optionPresentation.ownerLabel} · {optionPresentation.evidenceLabel}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          {blockedTransitionGroups.length ? (
            <div className="space-y-3 rounded-[0.95rem] border border-dashed border-slate-200 bg-slate-50 px-3 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Недоступно сейчас</p>
              {blockedTransitionGroups.map((group) => (
                <div key={group.label} className="space-y-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{group.label}</p>
                  <div className="grid gap-2 sm:grid-cols-2">
                    {group.options.map((option) => {
                      const optionPresentation = getTicketStatusPresentation({
                        status: option.value,
                        statusLabel: option.label,
                        requesterStatusLabel: ticket.requester_status_label,
                        nextActionOwner: getNextActionOwnerForStatus(option.value),
                        evidenceRequired: ticket.evidence_required,
                        evidenceRef: ticket.evidence_ref,
                      });
                      return (
                        <button
                          key={option.value}
                          className="rounded-[0.9rem] border border-slate-200 bg-white px-3 py-3 text-left text-slate-400"
                          disabled
                          type="button"
                        >
                          <span className="block text-sm font-semibold">{option.label}</span>
                          <span className="mt-1 block text-xs">
                            {optionPresentation.ownerLabel} · {option.blockedReason}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 rounded-[0.95rem] bg-surface-subtle px-3 py-3 text-sm">
        {disabledReason ? (
          <p className="mb-3 rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
            {disabledReason}
          </p>
        ) : null}
        {preview ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="font-medium text-slate-700">Предпросмотр перехода</span>
              <div className="flex flex-wrap gap-2">
                <Badge tone={preview.tone}>{preview.statusLabel}</Badge>
                <Badge tone={preview.tone}>{preview.stageLabel}</Badge>
              </div>
            </div>
            <div className="grid gap-2 text-slate-600 sm:grid-cols-2">
              <span>Текущий ход: {current.ownerLabel}</span>
              <span>Guard: {preview.evidenceLabel}</span>
            </div>
            <p className="text-slate-600">Следующий ответственный: {preview.ownerLabel}</p>
            {showClosureRequirements ? (
              <div className="rounded-[0.9rem] border border-slate-200 bg-white px-3 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">Чек-лист закрытия</p>
                  <Badge tone={closureRequirements.every((item) => item.met) ? "success" : "warning"}>
                    {closureRequirements.filter((item) => !item.met).length
                      ? `Не хватает: ${closureRequirements.filter((item) => !item.met).length}`
                      : "Готово"}
                  </Badge>
                </div>
                <div className="mt-3 grid gap-2">
                  {closureRequirements.map((item) => (
                    <div
                      className={cn(
                        "rounded-[0.75rem] border px-3 py-2",
                        item.met ? "border-emerald-100 bg-emerald-50/70" : "border-amber-200 bg-amber-50",
                      )}
                      key={item.key}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-medium text-slate-800">{item.label}</span>
                        <Badge tone={item.met ? "success" : "warning"}>{item.met ? "Есть" : "Нужно"}</Badge>
                      </div>
                      {item.detail ? <p className="mt-1 text-xs text-slate-600">{item.detail}</p> : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {evidenceBlocked ? (
              <p className="rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-amber-800">
                Перед решением нужен evidence или паспорт решения.
              </p>
            ) : selectedBlockedOption ? (
              <p className="rounded-[0.8rem] border border-slate-200 bg-white px-3 py-2 text-slate-600">
                Этот переход недоступен для текущего статуса.
              </p>
            ) : (
              <p className="text-slate-500">Сервер всё равно проверит FSM, evidence gate и права роли перед записью.</p>
            )}
          </div>
        ) : (
          <p className="text-slate-500">
            Текущий этап: <span className="font-medium text-slate-800">{current.stageLabel}</span>. Быстрое изменение не
            отправляется, пока оператор не подтвердит действие.
          </p>
        )}
      </div>
    </div>
  );
}