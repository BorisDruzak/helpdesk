import { CheckCircle2, Link2, Monitor, Search, ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

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
  requesterInvalidations,
  requesterTicketRouteParam,
  useRequesterBootstrapQuery,
  useRequesterDeviceDetailQuery,
} from "../../features/requester/queries";
import {
  confirmDevicePairing,
  fetchDevicePairing,
  lookupDevicePairingCode,
  type DevicePairingPayload,
} from "../device-pairing/api";
import { Button, FieldShell, InlineAlert, Input } from "../../features/requester/ui/form-controls";
import {
  isRegistrationPairing,
  resultDescription,
  resultTitle,
  type RequesterDevicesMode,
  type WizardStep,
} from "./devices-workflow";

export function RequesterDevicesPage() {
  return <RequesterDevicesWorkspace mode="overview" />;
}

export function RequesterDeviceLinkPage() {
  return <RequesterDevicesWorkspace mode="link" />;
}

function RequesterDevicesWorkspace({ mode }: { mode: RequesterDevicesMode }) {
  const location = useLocation();
  const queryClient = useQueryClient();
  const isLinkRoute = mode === "link";
  const bootstrapQuery = useRequesterBootstrapQuery();
  const bootstrap = bootstrapQuery.data;
  const devices = bootstrap?.devices ?? [];
  const pendingClaims = bootstrap?.pending_registration_claims ?? [];
  const directPairingId = useMemo(() => new URLSearchParams(location.search).get("pairing_id") || "", [location.search]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [pairing, setPairing] = useState<DevicePairingPayload | null>(null);
  const [step, setStep] = useState<WizardStep>(directPairingId ? "preview" : "code");
  const [notice, setNotice] = useState<string | null>(directPairingId ? "Проверьте устройство перед подключением." : null);
  const [error, setError] = useState<string | null>(null);
  const directPairingAttemptedRef = useRef<string | null>(null);
  const selectedDevice = selectedDeviceId ? devices.find((device) => device.device_id === selectedDeviceId) ?? null : null;
  const deviceDetailQuery = useRequesterDeviceDetailQuery(selectedDeviceId, { enabled: Boolean(selectedDeviceId) });

  const loadPairingMutation = useMutation({
    mutationFn: async (pairingId: string) => {
      const loaded = await fetchDevicePairing(pairingId);
      if (!isRegistrationPairing(loaded)) {
        throw new Error("Эта ссылка предназначена для входа на уже подключенном устройстве.");
      }
      return loaded;
    },
    onSuccess: (loaded) => {
      setPairing(loaded);
      setStep("preview");
      setNotice("Проверьте устройство перед подключением.");
      setError(null);
    },
    onError: (exc) => {
      setPairing(null);
      setStep("code");
      setNotice(null);
      setError(requesterErrorMessage(exc, "Не удалось загрузить устройство для подключения.", { domain: "device" }));
    },
  });

  const lookupMutation = useMutation({
    mutationFn: async (pairingCode: string) => {
      const lookup = await lookupDevicePairingCode(pairingCode);
      const loaded = await fetchDevicePairing(lookup.pairing_id);
      if (!isRegistrationPairing(loaded)) {
        throw new Error("Этот код предназначен для входа на уже подключенном устройстве.");
      }
      return loaded;
    },
    onSuccess: (loaded) => {
      setPairing(loaded);
      setStep("preview");
      setNotice("Проверьте устройство перед подключением.");
      setError(null);
    },
    onError: (exc) => {
      setPairing(null);
      setNotice(null);
      setError(requesterErrorMessage(exc, "Код подключения не найден или истек.", { domain: "device", operation: "device_link" }));
    },
  });

  const confirmMutation = useMutation({
    mutationFn: async () => {
      if (!pairing) {
        throw new Error("Сначала проверьте устройство.");
      }
      return confirmDevicePairing(pairing.pairing_id, "registration");
    },
    onSuccess: async (result) => {
      setPairing(result);
      setStep("result");
      setCode("");
      setNotice(resultTitle(result));
      setError(null);
      await requesterInvalidations.afterDeviceLink(queryClient);
    },
    onError: (exc) => {
      setError(requesterErrorMessage(exc, "Не удалось подключить устройство.", { domain: "device", operation: "device_link" }));
      setNotice(null);
    },
  });

  useEffect(() => {
    if (
      !directPairingId ||
      directPairingAttemptedRef.current === directPairingId ||
      pairing?.pairing_id === directPairingId ||
      loadPairingMutation.isPending
    ) {
      return;
    }
    directPairingAttemptedRef.current = directPairingId;
    loadPairingMutation.mutate(directPairingId);
  }, [directPairingId, loadPairingMutation, pairing?.pairing_id]);

  function submitCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = code.trim();
    setError(null);
    setNotice(null);
    if (!trimmed) {
      setError("Введите код подключения из агента.");
      return;
    }
    lookupMutation.mutate(trimmed);
  }

  if (bootstrapQuery.isLoading) {
    return <p className="text-sm text-slate-500">Загружаем устройства...</p>;
  }

  if (bootstrapQuery.error) {
    return (
      <section className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {requesterErrorMessage(bootstrapQuery.error, "Не удалось загрузить устройства", { domain: "device" })}
      </section>
    );
  }

  return (
    <div className="space-y-5">
      <header className="surface-panel px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="workspace-boot__eyebrow">Кабинет пользователя</p>
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">{isLinkRoute ? "Подключение устройства" : "Устройства"}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              {isLinkRoute
                ? "Введите код из локального агента или проверьте устройство по прямой ссылке. Подключение доступно до заполнения профиля."
                : "Основное устройство используется для диагностики и ускоряет обработку обычных обращений. Новое устройство можно подключить кодом из локального агента."}
            </p>
          </div>
          {isLinkRoute ? (
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800"
              to="/app/requester/devices"
            >
              К устройствам
            </Link>
          ) : (
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-3 py-2 text-sm font-semibold text-white"
              to="/app/requester/new?intent=device_owner_change"
            >
              <ShieldCheck className="h-4 w-4" />
              Проверить владельца
            </Link>
          )}
        </div>
      </header>

      <section className={isLinkRoute ? "grid gap-5 lg:max-w-xl" : "grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]"}>
        {!isLinkRoute ? (
        <div className="space-y-4">
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
                        <Button
                          onClick={() => setSelectedDeviceId(device.device_id)}
                          type="button"
                          variant="outline"
                        >
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

          {pendingClaims.length ? (
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
          ) : null}

          {selectedDevice ? (
            <section className="surface-panel px-5 py-4">
              <h2 className="text-lg font-semibold text-slate-950">Сведения об устройстве</h2>
              {deviceDetailQuery.isLoading ? <p className="mt-3 text-sm text-slate-500">Загружаем сведения...</p> : null}
              {deviceDetailQuery.error ? (
                <p className="mt-3 text-sm text-rose-700">
                  {requesterErrorMessage(deviceDetailQuery.error, "Не удалось загрузить сведения", { domain: "device" })}
                </p>
              ) : null}
              {deviceDetailQuery.data ? (
                <div className="mt-3 space-y-3">
                  <dl className="grid gap-2 text-sm sm:grid-cols-2">
                    <div className="rounded-panel border border-slate-200 px-3 py-2">
                      <dt className="text-xs font-semibold uppercase text-slate-500">Название</dt>
                      <dd className="mt-1 font-semibold text-slate-950">{requesterDeviceLabel(deviceDetailQuery.data.device)}</dd>
                    </div>
                    <div className="rounded-panel border border-slate-200 px-3 py-2">
                      <dt className="text-xs font-semibold uppercase text-slate-500">Доступ</dt>
                      <dd className="mt-1 font-semibold text-slate-950">{requesterRelationshipLabel(deviceDetailQuery.data.device.relationship_type)} · {requesterAccessStatusLabel(deviceDetailQuery.data.device.binding_status)}</dd>
                    </div>
                  </dl>
                  {deviceDetailQuery.data.recent_tickets?.length ? (
                    <div>
                      <p className="text-sm font-semibold text-slate-950">Последние обращения</p>
                      <ul className="mt-2 grid gap-2 text-sm">
                        {deviceDetailQuery.data.recent_tickets.map((ticket) => {
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
                  ) : null}
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
        ) : null}

        <aside className="space-y-4">
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
                  disabled={lookupMutation.isPending || confirmMutation.isPending}
                  onChange={(event) => setCode(event.target.value.toUpperCase())}
                  placeholder="ABCD-1234"
                  value={code}
                />
              </FieldShell>
              <Button
                disabled={lookupMutation.isPending || confirmMutation.isPending}
                leadingIcon={<Search className="h-4 w-4" />}
                type="submit"
                variant="outline"
              >
                {lookupMutation.isPending ? "Проверяем..." : "Проверить код"}
              </Button>
            </form>

            {step === "preview" && pairing ? (
              <div className="mt-4 rounded-panel border border-brand-200 bg-brand-50 px-3 py-3">
                <p className="text-sm font-semibold text-brand-950">{requesterDeviceLabel(pairing.device)}</p>
                <p className="mt-1 text-sm text-brand-900">{requesterDeviceSystemParts(pairing.device).join(" · ") || "Система не указана"}</p>
                <Button
                  className="mt-3 w-full"
                  disabled={confirmMutation.isPending}
                  leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                  onClick={() => confirmMutation.mutate()}
                  type="button"
                >
                  {confirmMutation.isPending ? "Подключаем..." : "Подключить устройство"}
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

          {!isLinkRoute ? (
          <section className="surface-panel px-5 py-4 text-sm text-slate-600">
            <p className="font-semibold text-slate-950">Проверка владельца</p>
            <p className="mt-2">
              Если компьютер должен перейти другому сотруднику или отображается не то рабочее место, создайте обращение. Поддержка проверит владельца без раскрытия внутренних идентификаторов.
            </p>
            <Link className="mt-3 inline-flex font-semibold text-brand-700" to="/app/requester/new?intent=device_owner_change">
              Создать запрос на проверку
            </Link>
          </section>
          ) : null}
        </aside>
      </section>
    </div>
  );
}
