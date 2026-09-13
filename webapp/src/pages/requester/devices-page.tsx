import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { requesterErrorMessage } from "../../features/requester/labels";
import {
  useRequesterBootstrapQuery,
  useRequesterDeviceDetailQuery,
} from "../../features/requester/queries";
import {
  DeviceDetailPanel,
  DevicesOverviewPanel,
  OwnerCheckAside,
  PendingDeviceClaimsPanel,
} from "./devices-panels";

export function RequesterDevicesPage() {
  const bootstrapQuery = useRequesterBootstrapQuery();
  const bootstrap = bootstrapQuery.data;
  const devices = bootstrap?.devices ?? [];
  const pendingClaims = bootstrap?.pending_registration_claims ?? [];
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const selectedDevice = selectedDeviceId ? devices.find((device) => device.device_id === selectedDeviceId) ?? null : null;
  const deviceDetailQuery = useRequesterDeviceDetailQuery(selectedDeviceId, { enabled: Boolean(selectedDeviceId) });

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
            <h1 className="mt-2 text-2xl font-semibold text-slate-950">Устройства</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
              Здесь отображаются ваши подтверждённые привязки. Если данные об устройстве или владельце неверны, создайте обращение для проверки.
            </p>
          </div>
          <Link
            className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-3 py-2 text-sm font-semibold text-white"
            to="/app/requester/new?intent=device_owner_change"
          >
            <ShieldCheck className="h-4 w-4" />
            Проверить владельца
          </Link>
        </div>
      </header>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
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
        <aside className="space-y-4">
          <OwnerCheckAside />
        </aside>
      </section>
    </div>
  );
}
