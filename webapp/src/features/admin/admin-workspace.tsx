import { useDeferredValue, useEffect, useState, startTransition } from "react";
import { useQuery } from "@tanstack/react-query";

import { DeviceUpdatePanel } from "../agent-updates/device-update-panel";
import { ObserverQuickPanel } from "../tech/observer-quick-panel";
import {
  type AdminStatusFilter,
  fetchAdminBootstrap,
  fetchAdminDevices,
} from "./api";


function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(date);
}


export function AdminWorkspace() {
  const [queryDraft, setQueryDraft] = useState("");
  const [statusFilter, setStatusFilter] = useState<AdminStatusFilter>("all");
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(queryDraft);

  const bootstrapQuery = useQuery({
    queryKey: ["admin-bootstrap"],
    queryFn: fetchAdminBootstrap,
    retry: false
  });

  const devicesQuery = useQuery({
    queryKey: ["admin-devices", statusFilter, deferredQuery],
    queryFn: () =>
      fetchAdminDevices({
        statusFilter,
        query: deferredQuery
      }),
    retry: false
  });

  const devices = devicesQuery.data?.devices ?? [];
  const selectedDevice =
    devices.find((item) => item.device_id === selectedDeviceId) ?? devices[0] ?? null;

  useEffect(() => {
    if (!devices.length) {
      if (selectedDeviceId !== null) {
        setSelectedDeviceId(null);
      }
      return;
    }

    if (!selectedDeviceId || !devices.some((item) => item.device_id === selectedDeviceId)) {
      setSelectedDeviceId(devices[0].device_id);
    }
  }, [devices, selectedDeviceId]);

  if (bootstrapQuery.isLoading || devicesQuery.isLoading) {
    return (
      <section className="workspace-boot workspace-boot--loading">
        <h1>Рабочее место администрирования</h1>
        <p>Собираем inventory устройств и rollout policy…</p>
      </section>
    );
  }

  if (bootstrapQuery.isError) {
    return (
      <section className="workspace-boot workspace-boot--error">
        <h1>Рабочее место администрирования</h1>
        <p>{bootstrapQuery.error instanceof Error ? bootstrapQuery.error.message : "Не удалось загрузить bootstrap admin workspace."}</p>
      </section>
    );
  }

  if (devicesQuery.isError || !devicesQuery.data) {
    return (
      <section className="workspace-boot workspace-boot--error">
        <h1>Рабочее место администрирования</h1>
        <p>{devicesQuery.error instanceof Error ? devicesQuery.error.message : "Не удалось загрузить inventory устройств."}</p>
      </section>
    );
  }

  const { summary, filters, rollout } = devicesQuery.data;
  const bootstrap = bootstrapQuery.data!;

  return (
    <section className="admin-workspace">
      <header className="workspace-boot__hero admin-workspace__hero">
        <div className="workspace-boot__hero-copy">
          <p className="workspace-boot__eyebrow">Контур управления</p>
          <h1>Рабочее место администрирования</h1>
          <p>
            Typed inventory для устройств и rollout-политик уже живёт здесь. Следующие slices
            будут расширять эту поверхность обновлениями агентов, модулями и observer drilldown.
          </p>
        </div>
        <dl className="workspace-boot__meta">
          <div>
            <dt>Всего в inventory</dt>
            <dd>{summary.visible_count}</dd>
          </div>
          <div>
            <dt>Онлайн сейчас</dt>
            <dd>{summary.online_count}</dd>
          </div>
          <div>
            <dt>Назначения rollout</dt>
            <dd>{summary.rollout_targets}</dd>
          </div>
        </dl>
      </header>

      <section className="admin-workspace__grid">
        <article className="support-workspace__panel">
          <div className="support-workspace__panel-head">
            <h2>Inventory устройств</h2>
            <p>Проверяем состав парка и readiness к rollout без legacy admin.js.</p>
          </div>

          <div className="support-filters admin-filters">
            <label className="support-filter-search">
              <span>Поиск по inventory</span>
              <input
                type="search"
                value={queryDraft}
                onChange={(event) => {
                  const value = event.currentTarget.value;
                  startTransition(() => {
                    setQueryDraft(value);
                  });
                }}
                placeholder="device_id, hostname, ОС или версия"
              />
            </label>
            <label className="support-filter-select">
              <span>Срез по связи</span>
              <select
                value={statusFilter}
                onChange={(event) => {
                  const value = event.currentTarget.value as AdminStatusFilter;
                  startTransition(() => {
                    setStatusFilter(value);
                  });
                }}
              >
                {filters.status_options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="admin-rollout">
            <div className="support-workspace__panel-head">
              <h3>Rollout policy</h3>
              <span>{bootstrap.features.join(" · ")}</span>
            </div>
            {rollout.length ? (
              <div className="admin-rollout__list">
                {rollout.map((item) => (
                  <article key={`${item.target}:${item.channel}:${item.version}`} className="workspace-card">
                    <p className="workspace-card__code">{item.target}</p>
                    <h3>{item.channel}/{item.version}</h3>
                    <p>
                      {item.updated_by ? `Обновил ${item.updated_by}` : "Источник обновления не указан"}
                    </p>
                    <p>Изменено: {formatDateTime(item.updated_at)}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="support-queue-empty">Назначений rollout пока нет. Новый boundary уже готов их показывать.</div>
            )}
          </div>

          {devices.length ? (
            <div className="admin-device-list">
              {devices.map((device) => (
                <button
                  key={device.device_id}
                  type="button"
                  className={`support-ticket-card admin-device-card${selectedDevice?.device_id === device.device_id ? " active" : ""}`}
                  onClick={() => {
                    startTransition(() => {
                      setSelectedDeviceId(device.device_id);
                    });
                  }}
                >
                  <div className="support-ticket-card__head">
                    <strong>{device.hostname ?? device.device_id}</strong>
                    <span className="support-ticket-card__status">{device.connection_status_label}</span>
                  </div>
                  <div className="support-ticket-card__meta">
                    <span>{device.target ?? "target не определён"}</span>
                    <span>{device.agent_version ?? "версия не указана"}</span>
                  </div>
                  <p>{device.latest_update.summary ?? "Нет свежих rollout-данных."}</p>
                </button>
              ))}
            </div>
          ) : (
            <div className="support-queue-empty">
              Под текущий фильтр пока не попало ни одного устройства.
            </div>
          )}
        </article>

        <article className="support-workspace__panel">
          <div className="support-workspace__panel-head">
            <h2>Карточка устройства</h2>
            <p>Typed detail-panel уже ведёт update workflow и первый observer quick срез без legacy admin.js.</p>
          </div>

          {selectedDevice ? (
            <section className="admin-device-detail">
              <div className="support-ticket-detail__hero">
                <div className="support-ticket-detail__block">
                  <p className="support-ticket-detail__code">{selectedDevice.device_id}</p>
                  <h3>{selectedDevice.hostname ?? "Имя узла не указано"}</h3>
                  <p>{selectedDevice.os ?? "ОС не определена"}</p>
                </div>
                <dl className="support-ticket-detail__stats">
                  <div>
                    <dt>Состояние</dt>
                    <dd>{selectedDevice.connection_status_label}</dd>
                  </div>
                  <div>
                    <dt>Target</dt>
                    <dd>{selectedDevice.target ?? "—"}</dd>
                  </div>
                  <div>
                    <dt>Последний контакт</dt>
                    <dd>{formatDateTime(selectedDevice.last_seen_at)}</dd>
                  </div>
                </dl>
              </div>

              <div className="support-ticket-detail__grid">
                <article className="support-snapshot-card">
                  <span>Версия агента</span>
                  <strong>{selectedDevice.agent_version ?? "Неизвестно"}</strong>
                  <p>Этот срез нужен для будущих rollout-решений и bulk update flows.</p>
                </article>
                <article className="support-snapshot-card">
                  <span>Update readiness</span>
                  <strong>{selectedDevice.latest_update.label}</strong>
                  <p>{selectedDevice.latest_update.summary ?? "Нет свежих данных по update workflow."}</p>
                </article>
                <article className="support-snapshot-card">
                  <span>Observer surface</span>
                  <strong>{bootstrap.observer.quick_endpoint}</strong>
                  <p>Этот же workspace теперь показывает живой quick-срез по трассам и dangerous flows.</p>
                </article>
              </div>

              <DeviceUpdatePanel
                device={{
                  device_id: selectedDevice.device_id,
                  hostname: selectedDevice.hostname
                }}
              />
              <ObserverQuickPanel />
            </section>
          ) : (
            <div className="support-ticket-empty">Выберите устройство слева, чтобы открыть detail-panel.</div>
          )}
        </article>
      </section>
    </section>
  );
}
