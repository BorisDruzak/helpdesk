import { CheckCircle2, KeyRound, Monitor, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import {
  confirmDevicePairing,
  DevicePairingApiError,
  fetchDevicePairing,
  fetchRegistryOptions,
  lookupDevicePairingCode,
  type DevicePairingPayload,
  type DevicePairingPurpose,
  type RegistryOption,
} from "./api";

type DevicePairingPageProps = {
  purpose: DevicePairingPurpose;
};

function formatValue(value?: string | null) {
  return value && value.trim() ? value : "Не указано";
}

function purposeText(purpose: DevicePairingPurpose) {
  if (purpose === "registration") {
    return {
      action: "Подтвердить привязку",
      done: "Привязка устройства подтверждена",
      heading: "Регистрация устройства",
      intro:
        "Подтвердите, что этот компьютер можно связать с вашим аккаунтом. Если политика требует проверки, заявка уйдет администратору.",
    };
  }
  return {
    action: "Подтвердить вход",
    done: "Вход подтвержден",
    heading: "Вход на этом устройстве",
    intro: "Подтвердите вход в локальный агент на указанном компьютере.",
  };
}

const DEVICE_LINK_STATUS_LABELS: Record<string, string> = {
  canceled: "Отменено",
  confirmed: "Подтверждено",
  expired: "Срок действия истёк",
  pending: "Ожидает подтверждения",
  rejected: "Отклонено",
};

const REGISTRATION_STATUS_LABELS: Record<string, string> = {
  active: "Устройство привязано",
  admin_confirmed: "Устройство привязано",
  approved: "Устройство привязано",
  conflict: "Требуется проверка администратора",
  pending_admin_review: "Ожидает проверки администратора",
  pending_user_confirmation: "Ожидает подтверждения",
  pending_verification: "Ожидает проверки",
  rejected: "Отклонено администратором",
  self_reported: "Ожидает проверки",
  user_confirmed: "Ожидает проверки администратора",
};

function productStatusLabel(status: string | null | undefined, labels: Record<string, string>) {
  const normalized = status?.trim().toLowerCase();
  return normalized ? labels[normalized] ?? "Статус уточняется" : "Статус не указан";
}

function deviceLinkStatusLabel(status: string | null | undefined) {
  return productStatusLabel(status, DEVICE_LINK_STATUS_LABELS);
}

function registrationStatusLabel(status: string | null | undefined) {
  return productStatusLabel(status, REGISTRATION_STATUS_LABELS);
}

function registrationDoneHint(status: string | null | undefined) {
  const normalized = status?.trim().toLowerCase();
  if (normalized === "pending_admin_review" || normalized === "user_confirmed" || normalized === "conflict") {
    return "Администратор должен одобрить заявку. В локальном агенте нажмите «Обновить», чтобы увидеть статус ожидания.";
  }
  if (normalized === "approved" || normalized === "admin_confirmed" || normalized === "active") {
    return "Вернитесь в локальный агент и нажмите «Обновить», чтобы войти под привязанным пользователем.";
  }
  return "Вернитесь в локальный агент и нажмите «Обновить», чтобы увидеть актуальный статус.";
}

function registrationDoneTitle(status: string | null | undefined) {
  const normalized = status?.trim().toLowerCase();
  if (normalized === "approved" || normalized === "admin_confirmed" || normalized === "active") {
    return "Устройство привязано";
  }
  if (normalized === "pending_admin_review" || normalized === "user_confirmed" || normalized === "conflict") {
    return "Заявка на привязку отправлена";
  }
  return "Привязка устройства подтверждена";
}

function withNextPath(path: string, nextPath: string) {
  const url = new URL(path, "https://pc-client.local");
  url.searchParams.set("next", nextPath);
  return `${url.pathname}${url.search}`;
}

export function DevicePairCodePage() {
  const navigate = useNavigate();
  const [pairingCode, setPairingCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = pairingCode.trim();
    if (!code) {
      setError("Введите код подключения");
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      const payload = await lookupDevicePairingCode(code);
      const routePurpose = payload.purpose === "registration" ? "register" : "login";
      const nextUrl = payload.next_url || `/app/device/${routePurpose}?pairing_id=${encodeURIComponent(payload.pairing_id)}`;
      navigate(nextUrl, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Код подключения не найден или истек");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="min-h-screen bg-app px-4 py-8">
      <div className="mx-auto max-w-xl space-y-6">
        <div className="space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">pc_client</p>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-950">Подключение устройства</h1>
          <p className="max-w-2xl text-sm leading-7 text-slate-500">
            Введите код из локального агента, чтобы открыть подтверждение входа или регистрации.
          </p>
        </div>

        <form className="rounded-[0.5rem] border border-border bg-white p-6 shadow-soft" onSubmit={handleSubmit}>
          <div className="space-y-5">
            <div className="flex items-start gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-[0.5rem] bg-brand-50 text-brand-700">
                <KeyRound className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <label className="text-sm font-semibold text-slate-900" htmlFor="device-pairing-code">
                  Код подключения
                </label>
                <input
                  autoComplete="one-time-code"
                  autoFocus
                  className="mt-2 h-12 w-full rounded-[0.5rem] border border-border bg-white px-3 font-mono text-base font-semibold uppercase text-slate-950 outline-none transition-colors placeholder:text-slate-400 focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
                  id="device-pairing-code"
                  inputMode="text"
                  maxLength={16}
                  onChange={(event) => setPairingCode(event.target.value.toUpperCase())}
                  placeholder="ABCD-1234"
                  value={pairingCode}
                />
              </div>
            </div>

            {error ? (
              <div className="flex items-start gap-3 rounded-[0.5rem] bg-rose-50 px-4 py-3 text-rose-700">
                <XCircle className="mt-0.5 h-5 w-5" />
                <p className="text-sm">{error}</p>
              </div>
            ) : null}

            <Button disabled={isSubmitting} leadingIcon={<ShieldCheck className="h-4 w-4" />} type="submit">
              {isSubmitting ? "Проверяем..." : "Продолжить"}
            </Button>
          </div>
        </form>
      </div>
    </section>
  );
}

export function DevicePairingPage({ purpose }: DevicePairingPageProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const pairingId = searchParams.get("pairing_id") ?? "";
  const [pairing, setPairing] = useState<DevicePairingPayload | null>(null);
  const [confirmed, setConfirmed] = useState<DevicePairingPayload | null>(null);
  const [departments, setDepartments] = useState<RegistryOption[]>([]);
  const [locations, setLocations] = useState<RegistryOption[]>([]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState("");
  const [selectedLocationId, setSelectedLocationId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isConfirming, setIsConfirming] = useState(false);
  const copy = useMemo(() => purposeText(purpose), [purpose]);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);

    void (async () => {
      try {
        if (!pairingId) {
          throw new DevicePairingApiError(
            "Откройте эту страницу из агента или введите код подключения.",
            400,
            "PAIRING_ID_REQUIRED",
          );
        }
        const [payload, options] = await Promise.all([
          fetchDevicePairing(pairingId),
          purpose === "registration" ? fetchRegistryOptions() : Promise.resolve(null),
        ]);
        if (!active) {
          return;
        }
        setPairing(payload);
        if (options) {
          setDepartments(options.departments ?? []);
          setLocations(options.locations ?? []);
          setSelectedDepartmentId("");
          setSelectedLocationId("");
        }
      } catch (err) {
        if (!active) {
          return;
        }
        setError(err instanceof Error ? err.message : "Не удалось загрузить привязку устройства");
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [pairingId, purpose]);

  async function handleConfirm() {
    if (!pairingId) {
      return;
    }
    setError(null);
    setIsConfirming(true);
    try {
      const payload = await confirmDevicePairing(
        pairingId,
        purpose,
        purpose === "registration"
          ? {
              ...(selectedDepartmentId ? { department_id: selectedDepartmentId } : {}),
              ...(selectedLocationId ? { location_id: selectedLocationId } : {}),
            }
          : {},
      );
      const nextPayload = {
        ...payload,
        device: payload.device ?? pairing?.device ?? confirmed?.device,
      };
      setConfirmed(nextPayload);
      setPairing(nextPayload);
    } catch (err) {
      if (err instanceof DevicePairingApiError && err.errorCode === "REQUESTER_PROFILE_INCOMPLETE") {
        const nextPath = `${location.pathname}${location.search}${location.hash}`;
        navigate(withNextPath("/app/requester/profile/setup", nextPath), { replace: true });
        return;
      }
      setError(err instanceof Error ? err.message : "Не удалось подтвердить устройство");
    } finally {
      setIsConfirming(false);
    }
  }

  const device = pairing?.device ?? confirmed?.device ?? null;
  const isDone = Boolean(confirmed);

  return (
    <section className="min-h-screen bg-app px-4 py-8">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-brand-700">pc_client</p>
          <h1 className="font-display text-3xl font-semibold tracking-tight text-slate-950">{copy.heading}</h1>
          <p className="max-w-2xl text-sm leading-7 text-slate-500">{copy.intro}</p>
        </div>

        <div className="rounded-[0.5rem] border border-border bg-white p-6 shadow-soft">
          {isLoading ? (
            <p className="text-sm text-slate-500">Загружаем данные устройства...</p>
          ) : error ? (
            <div className="flex items-start gap-3 text-rose-700">
              <XCircle className="mt-0.5 h-5 w-5" />
              <p className="text-sm">{error}</p>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-[0.5rem] bg-brand-50 text-brand-700">
                  <Monitor className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-500">Устройство</p>
                  <h2 className="mt-1 text-xl font-semibold text-slate-950">{formatValue(device?.hostname)}</h2>
                </div>
              </div>

              <dl className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-[0.5rem] bg-surface-subtle px-4 py-3">
                  <dt className="text-xs font-medium text-slate-500">ОС</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-900">{formatValue(device?.os)}</dd>
                </div>
                <div className="rounded-[0.5rem] bg-surface-subtle px-4 py-3">
                  <dt className="text-xs font-medium text-slate-500">Версия агента</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-900">{formatValue(device?.agent_version)}</dd>
                </div>
                <div className="rounded-[0.5rem] bg-surface-subtle px-4 py-3">
                  <dt className="text-xs font-medium text-slate-500">{purpose === "registration" ? "Статус заявки" : "Статус"}</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-900">
                    {deviceLinkStatusLabel(confirmed?.status ?? pairing?.status)}
                  </dd>
                </div>
              </dl>

              {isDone ? (
                <div className="flex items-start gap-3 rounded-[0.5rem] bg-emerald-50 px-4 py-3 text-emerald-800">
                  <CheckCircle2 className="mt-0.5 h-5 w-5" />
                  <div>
                    <p className="font-semibold">
                      {purpose === "registration" ? registrationDoneTitle(confirmed?.registration?.status) : copy.done}
                    </p>
                    {confirmed?.registration?.status ? (
                      <>
                        <p className="mt-1 text-sm">{registrationStatusLabel(confirmed.registration.status)}</p>
                        <p className="mt-1 text-sm">{registrationDoneHint(confirmed.registration.status)}</p>
                      </>
                    ) : (
                      <p className="mt-1 text-sm">Вернитесь в локальный агент, он получит результат автоматически.</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {purpose === "registration" && (departments.length || locations.length) ? (
                    <div className="grid gap-4 sm:grid-cols-2">
                      {departments.length ? (
                        <label className="block text-sm font-semibold text-slate-900">
                          Подразделение
                          <select
                            className="mt-2 h-11 w-full rounded-[0.5rem] border border-border bg-white px-3 text-sm text-slate-950 outline-none transition-colors focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
                            disabled={isConfirming}
                            onChange={(event) => setSelectedDepartmentId(event.target.value)}
                            value={selectedDepartmentId}
                          >
                            <option value="">Не выбрано</option>
                            {departments.map((department) => (
                              <option key={department.value} value={department.value}>
                                {department.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                      {locations.length ? (
                        <label className="block text-sm font-semibold text-slate-900">
                          Локация
                          <select
                            className="mt-2 h-11 w-full rounded-[0.5rem] border border-border bg-white px-3 text-sm text-slate-950 outline-none transition-colors focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
                            disabled={isConfirming}
                            onChange={(event) => setSelectedLocationId(event.target.value)}
                            value={selectedLocationId}
                          >
                            <option value="">Не выбрано</option>
                            {locations.map((location) => (
                              <option key={location.value} value={location.value}>
                                {location.label}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                    </div>
                  ) : null}
                  <Button
                    disabled={isConfirming || pairing?.purpose !== purpose || pairing?.status !== "pending"}
                    leadingIcon={<ShieldCheck className="h-4 w-4" />}
                    onClick={handleConfirm}
                  >
                    {isConfirming ? "Подтверждаем..." : copy.action}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
