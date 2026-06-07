import { CheckCircle2, Monitor, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Button } from "../../components/ui/button";
import {
  confirmDevicePairing,
  DevicePairingApiError,
  fetchDevicePairing,
  type DevicePairingPayload,
  type DevicePairingPurpose,
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
      action: "Подтвердить регистрацию",
      done: "Регистрация подтверждена",
      heading: "Регистрация устройства",
      intro: "Подтвердите, что этот компьютер можно связать с вашим аккаунтом.",
    };
  }
  return {
    action: "Подтвердить вход",
    done: "Вход подтвержден",
    heading: "Вход на этом устройстве",
    intro: "Подтвердите вход в локальный агент на указанном компьютере.",
  };
}

export function DevicePairingPage({ purpose }: DevicePairingPageProps) {
  const [searchParams] = useSearchParams();
  const pairingId = searchParams.get("pairing_id") ?? "";
  const [pairing, setPairing] = useState<DevicePairingPayload | null>(null);
  const [confirmed, setConfirmed] = useState<DevicePairingPayload | null>(null);
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
          throw new DevicePairingApiError("Не указан pairing_id", 400, "PAIRING_ID_REQUIRED");
        }
        const payload = await fetchDevicePairing(pairingId);
        if (!active) {
          return;
        }
        setPairing(payload);
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
  }, [pairingId]);

  async function handleConfirm() {
    if (!pairingId) {
      return;
    }
    setError(null);
    setIsConfirming(true);
    try {
      const payload = await confirmDevicePairing(pairingId, purpose);
      setConfirmed(payload);
      setPairing(payload);
    } catch (err) {
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
                  <dt className="text-xs font-medium text-slate-500">Статус</dt>
                  <dd className="mt-1 text-sm font-semibold text-slate-900">{confirmed?.status ?? pairing?.status}</dd>
                </div>
              </dl>

              {isDone ? (
                <div className="flex items-start gap-3 rounded-[0.5rem] bg-emerald-50 px-4 py-3 text-emerald-800">
                  <CheckCircle2 className="mt-0.5 h-5 w-5" />
                  <div>
                    <p className="font-semibold">{copy.done}</p>
                    {confirmed?.registration?.status ? (
                      <p className="mt-1 text-sm">{confirmed.registration.status}</p>
                    ) : (
                      <p className="mt-1 text-sm">Вернитесь в локальный агент, он получит результат автоматически.</p>
                    )}
                  </div>
                </div>
              ) : (
                <Button
                  disabled={isConfirming || pairing?.purpose !== purpose || pairing?.status !== "pending"}
                  leadingIcon={<ShieldCheck className="h-4 w-4" />}
                  onClick={handleConfirm}
                >
                  {isConfirming ? "Подтверждаем..." : copy.action}
                </Button>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
