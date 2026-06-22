import { ShieldCheck } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { requesterErrorMessage } from "../../features/requester/labels";
import {
  requesterInvalidations,
  useRequesterBootstrapQuery,
  useRequesterDeviceDetailQuery,
} from "../../features/requester/queries";
import {
  confirmDevicePairing,
  fetchDevicePairing,
  lookupDevicePairingCode,
  type DevicePairingPayload,
} from "../device-pairing/api";
import {
  DeviceDetailPanel,
  DevicePairingAside,
  DevicesOverviewPanel,
  OwnerCheckAside,
  PendingDeviceClaimsPanel,
} from "./devices-panels";
import {
  isRegistrationPairing,
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
            <DevicesOverviewPanel devices={devices} onSelectDevice={setSelectedDeviceId} />
            <PendingDeviceClaimsPanel pendingClaims={pendingClaims} />
            {selectedDevice ? (
              <DeviceDetailPanel
                data={deviceDetailQuery.data}
                error={deviceDetailQuery.error}
                isLoading={deviceDetailQuery.isLoading}
              />
            ) : null}
          </div>
        ) : null}

        <aside className="space-y-4">
          <DevicePairingAside
            code={code}
            confirmPending={confirmMutation.isPending}
            error={error}
            lookupPending={lookupMutation.isPending}
            notice={notice}
            onCodeChange={setCode}
            onConfirm={() => confirmMutation.mutate()}
            pairing={pairing}
            step={step}
            submitCode={submitCode}
          />
          {!isLinkRoute ? <OwnerCheckAside /> : null}
        </aside>
      </section>
    </div>
  );
}
