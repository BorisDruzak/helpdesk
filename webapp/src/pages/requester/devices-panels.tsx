import { CheckCircle2, Link2, Monitor, Search } from "lucide-react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";

import { formatRussianDateTime } from "../../components/ui-page";
import {
  requesterAccessStatusLabel,
  requesterDeviceLabel,
  requesterDeviceSystemParts,
  requesterErrorMessage,
  requesterOnlineStatusLabel,
  requesterPendingDeviceStatusLabel,
  requesterRelationshipLabel,
} from "../../features/requester/labels";
import {
  humanRequesterTicketCode,
  requesterTicketRouteParam,
} from "../../features/requester/queries";
import type {
  AuthenticatedRequesterTicket,
  RequesterDevice,
  RequesterDeviceDetail,
  RequesterPendingRegistrationClaim,
} from "../../features/requester/types";
import { Button, FieldShell, InlineAlert, Input } from "../../features/requester/ui/form-controls";
import type { DevicePairingPayload } from "../device-pairing/api";
import { resultDescription, resultTitle, type WizardStep } from "./devices-workflow";

export function DevicesOverviewPanel({
  devices,
  onSelectDevice,
}: {
  devices: RequesterDevice[];
  onSelectDevice: (deviceId: string) => void;
}) {
  return (
    <section className="surface-panel px-5 py-4">
      <h2 className="text-lg font-semibold text-slate-950">Мои устройства</h2>
      <p className="mt-1 text-sm text-slate-600">
        Для обращения не нужно выбирать диагностическую цель вручную: поддержка использует подтвержденное основное устройство или уточнит контекст в обращении.
      </p>
      <div className="mt-4 grid gap-3">
        {devices.length ? (
          devices.map((device) => {
            const name = requesterDeviceLabel(device);
            return (
              <article className="rounded-panel border border-slate-200 bg-white px-4 py-3" key={device.device_id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Monitor className="h-4 w-4 text-brand-700" />
                      <h3 className="break-words text-base font-semibold text-slate-950">{name}</h3>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
                      <span className="rounded-panel bg-emerald-50 px-2 py-1 text-emerald-700">{requesterRelationshipLabel(device.relationship_type)}</span>
                      <span className="rounded-panel bg-slate-100 px-2 py-1 text-slate-700">{requesterAccessStatusLabel(device.binding_status)}</span>
                      <span className="rounded-panel bg-slate-100 px-2 py-1 text-slate-700">{requesterOnlineStatusLabel(device.online)}</span>
                    </div>
                  </div>
                  <Button onClick={() => onSelectDevice(device.device_id)} type="button" variant="outline">
                    Подробнее о {name}
                  </Button>
                </div>
                <dl className="mt-3 grid gap-2 text-sm text-slate-600 sm:grid-cols-3">
                  <div>
                    <dt className="font-semibold text-slate-500">Система</dt>
                    <dd className="mt-1 text-slate-950">{requesterDeviceSystemParts(device).join(" · ") || "Не указана"}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-500">Активность</dt>
                    <dd className="mt-1 text-slate-950">{formatRussianDateTime(device.last_seen_at, { emptyText: "Пока нет данных" })}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-500">Обращения</dt>
                    <dd className="mt-1 text-slate-950">Открытые обращения: {device.open_ticket_count ?? 0}</dd>
                  </div>
                </dl>
              </article>
            );
          })
        ) : (
          <div className="rounded-panel border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-600">
            Подтвержденных устройств пока нет. Подключите агент кодом или создайте обращение на проверку владельца.
          </div>
        )}
      </div>
    </section>
  );
}

export function PendingDeviceClaimsPanel({ pendingClaims }: { pendingClaims: RequesterPendingRegistrationClaim[] }) {
  if (!pendingClaims.length) {
    return null;
  }
  return (
    <section className="surface-panel px-5 py-4">
      <h2 className="text-lg font-semibold text-slate-950">Запросы на подключение</h2>
      <div className="mt-3 grid gap-2">
        {pendingClaims.map((claim, index) => (
          <div className="rounded-panel border border-amber-200 bg-amber-50 px-3 py-2 text-sm" key={claim.claim_id || `${claim.status}-${index}`}>
            <p className="font-semibold text-amber-950">Устройство ожидает проверки</p>
            <p className="mt-1 text-amber-800">{requesterPendingDeviceStatusLabel(claim)}</p>
            {claim.submitted_at ? (
              <p className="mt-1 text-xs text-amber-800">Отправлено {formatRussianDateTime(claim.submitted_at)}</p>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}

export function DeviceDetailPanel({
  data,
  error,
  isLoading,
}: {
  data: RequesterDeviceDetail | undefined;
  error: unknown;
  isLoading: boolean;
}) {
  return (
    <section className="surface-panel px-5 py-4">
      <h2 className="text-lg font-semibold text-slate-950">Сведения об устройстве</h2>
      {isLoading ? <p className="mt-3 text-sm text-slate-500">Загружаем сведения...</p> : null}
      {error ? (
        <p className="mt-3 text-sm text-rose-700">
          {requesterErrorMessage(error, "Не удалось загрузить сведения", { domain: "device" })}
        </p>
      ) : null}
      {data ? (
        <div className="mt-3 space-y-3">
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <div className="rounded-panel border border-slate-200 px-3 py-2">
              <dt className="text-xs font-semibold uppercase text-slate-500">Название</dt>
              <dd className="mt-1 font-semibold text-slate-950">{requesterDeviceLabel(data.device)}</dd>
            </div>
            <div className="rounded-panel border border-slate-200 px-3 py-2">
              <dt className="text-xs font-semibold uppercase text-slate-500">Доступ</dt>
              <dd className="mt-1 font-semibold text-slate-950">{requesterRelationshipLabel(data.device.relationship_type)} · {requesterAccessStatusLabel(data.device.binding_status)}</dd>
            </div>
          </dl>
          {data.recent_tickets?.length ? <RecentDeviceTickets tickets={data.recent_tickets} /> : null}
        </div>
      ) : null}
    </section>
  );
}

function RecentDeviceTickets({ tickets }: { tickets: AuthenticatedRequesterTicket[] }) {
  return (
    <div>
      <p className="text-sm font-semibold text-slate-950">Последние обращения</p>
      <ul className="mt-2 grid gap-2 text-sm">
        {tickets.map((ticket) => {
          const routeParam = requesterTicketRouteParam(ticket);
          return (
            <li className="rounded-panel border border-slate-200 px-3 py-2" key={ticket.ticket_id}>
              {routeParam ? (
                <Link className="font-semibold text-brand-700" to={`/app/requester/tickets/${encodeURIComponent(routeParam)}`}>
                  {humanRequesterTicketCode(ticket)}
                </Link>
              ) : (
                <span className="font-semibold text-slate-700">{humanRequesterTicketCode(ticket)}</span>
              )}
              <span className="ml-2 text-slate-600">{ticket.title || "Без темы"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DevicePairingAside({
  code,
  confirmPending,
  error,
  lookupPending,
  notice,
  onCodeChange,
  onConfirm,
  pairing,
  step,
  submitCode,
}: {
  code: string;
  confirmPending: boolean;
  error: string | null;
  lookupPending: boolean;
  notice: string | null;
  onCodeChange: (value: string) => void;
  onConfirm: () => void;
  pairing: DevicePairingPayload | null;
  step: WizardStep;
  submitCode: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="surface-panel px-5 py-4">
      <div className="flex items-center gap-2">
        <Link2 className="h-4 w-4 text-brand-700" />
        <h2 className="text-lg font-semibold text-slate-950">Подключить устройство</h2>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Код создается в локальном агенте. Подключение доступно даже до заполнения профиля.
      </p>

      <form className="mt-4 grid gap-3" onSubmit={submitCode}>
        <FieldShell label="Код подключения">
          <Input
            aria-label="Код подключения"
            className="mt-1 w-full text-sm uppercase text-slate-950"
            disabled={lookupPending || confirmPending}
            onChange={(event) => onCodeChange(event.target.value.toUpperCase())}
            placeholder="ABCD-1234"
            value={code}
          />
        </FieldShell>
        <Button disabled={lookupPending || confirmPending} leadingIcon={<Search className="h-4 w-4" />} type="submit" variant="outline">
          {lookupPending ? "Проверяем..." : "Проверить код"}
        </Button>
      </form>

      {step === "preview" && pairing ? (
        <div className="mt-4 rounded-panel border border-brand-200 bg-brand-50 px-3 py-3">
          <p className="text-sm font-semibold text-brand-950">{requesterDeviceLabel(pairing.device)}</p>
          <p className="mt-1 text-sm text-brand-900">{requesterDeviceSystemParts(pairing.device).join(" · ") || "Система не указана"}</p>
          <Button className="mt-3 w-full" disabled={confirmPending} leadingIcon={<CheckCircle2 className="h-4 w-4" />} onClick={onConfirm} type="button">
            {confirmPending ? "Подключаем..." : "Подключить устройство"}
          </Button>
        </div>
      ) : null}

      {step === "result" ? (
        <div className="mt-4 rounded-panel border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-800">
          <p className="font-semibold text-emerald-950">{resultTitle(pairing)}</p>
          <p className="mt-1">{resultDescription(pairing)}</p>
        </div>
      ) : null}

      {notice && step !== "result" ? <InlineAlert aria-live="polite" className="mt-3" role="status" tone="success">{notice}</InlineAlert> : null}
      {error ? <InlineAlert aria-live="assertive" className="mt-3" role="alert" tone="danger">{error}</InlineAlert> : null}
    </section>
  );
}

export function OwnerCheckAside() {
  return (
    <section className="surface-panel px-5 py-4 text-sm text-slate-600">
      <p className="font-semibold text-slate-950">Проверка владельца</p>
      <p className="mt-2">
        Если компьютер должен перейти другому сотруднику или отображается не то рабочее место, создайте обращение. Поддержка проверит владельца без раскрытия внутренних идентификаторов.
      </p>
      <Link className="mt-3 inline-flex font-semibold text-brand-700" to="/app/requester/new?intent=device_owner_change">
        Создать запрос на проверку
      </Link>
    </section>
  );
}
