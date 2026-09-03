import { useDeferredValue, useEffect, useState, startTransition } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { FormsBuilderPanel } from "../forms-builder/forms-builder-panel";
import { ModulesPanel } from "../modules/modules-panel";
import { ObserverQuickPanel } from "../tech/observer-quick-panel";
import { getSharedWebRealtimeClient } from "../../shared/realtime/client";
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
    timeStyle: "short",
  }).format(date);
}

export function AdminWorkspace() {
  const queryClient = useQueryClient();
  const [queryDraft, setQueryDraft] = useState("");
  const [statusFilter, setStatusFilter] = useState<AdminStatusFilter>("all");
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(queryDraft);

  const bootstrapQuery = useQuery({
    queryKey: ["admin-bootstrap"],
    queryFn: fetchAdminBootstrap,
    retry: false,
  });

  const devicesQuery = useQuery({
    queryKey: ["admin-devices", statusFilter, deferredQuery],
    queryFn: () =>
      fetchAdminDevices({
        statusFilter,
        query: deferredQuery,
      }),
    retry: false,
  });

  const devices = devicesQuery.data?.devices ?? [];
  const selectedDevice = devices.find((item) => item.device_id === selectedDeviceId) ?? devices[0] ?? null;

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

  const visibleDeviceIds = devices.map((device) => device.device_id);
  const visibleDeviceIdsKey = visibleDeviceIds.join("|");

  useEffect(() => {
    if (!visibleDeviceIds.length) {
      return;
    }

    const realtimeClient = getSharedWebRealtimeClient();
    const unsubscribers = visibleDeviceIds.map((deviceId) =>
      realtimeClient.subscribeDevice(deviceId, (message) => {
        void queryClient.invalidateQueries({ queryKey: ["admin-devices"] });
        if (message.deviceId !== selectedDevice?.device_id) {
          return;
        }
        void queryClient.invalidateQueries({ queryKey: ["admin-device-updates", selectedDevice.device_id] });
        void queryClient.invalidateQueries({ queryKey: ["admin-observer-quick", selectedDevice.device_id] });
        void queryClient.invalidateQueries({ queryKey: ["admin-observer-traces", selectedDevice.device_id] });
        void queryClient.invalidateQueries({ queryKey: ["admin-observer-trace-detail"] });
      }),
    );

    return () => {
      for (const unsubscribe of unsubscribers) {
        unsubscribe();
      }
    };
  }, [queryClient, selectedDevice?.device_id, visibleDeviceIdsKey]);

  if (bootstrapQuery.isLoading || devicesQuery.isLoading) {
    return (
      <section className="workspace-boot workspace-boot--loading">
        <div className="workspace-boot__hero">
          <div className="workspace-boot__hero-copy">
            <p className="workspace-boot__eyebrow">Контур управления</p>
            <h1>Рабочее место администрирования</h1>
            <p>Собираем инвентарь устройств, политику rollout и быстрый observer-срез…</p>
          </div>
        </div>
      </section>
    );
  }

  if (bootstrapQuery.isError) {
    return (
      <section className="workspace-boot workspace-boot--error">
        <div className="workspace-boot__hero">
          <div className="workspace-boot__hero-copy">
            <p className="workspace-boot__eyebrow">Контур управления</p>
            <h1>Рабочее место администрирования</h1>
            <p>
              {bootstrapQuery.error instanceof Error
                ? bootstrapQuery.error.message
                : "Не удалось загрузить стартовую конфигурацию рабочего места администрирования."}
            </p>
          </div>
        </div>
      </section>
    );
  }

  if (devicesQuery.isError || !devicesQuery.data) {
    return (
      <section className="workspace-boot workspace-boot--error">
        <div className="workspace-boot__hero">
          <div className="workspace-boot__hero-copy">
            <p className="workspace-boot__eyebrow">Контур управления</p>
            <h1>Рабочее место администрирования</h1>
            <p>
              {devicesQuery.error instanceof Error
                ? devicesQuery.error.message
                : "Не удалось загрузить инвентарь устройств."}
            </p>
          </div>
        </div>
      </section>
    );
  }

  const { summary, filters, rollout } = devicesQuery.data;
  const bootstrap = bootstrapQuery.data!;

  return (
    <section className="admin-workspace workspace-page">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Контур управления</p>
          <h1>Рабочее место администрирования</h1>
          <p>
            Тот же единый shell, что и в поддержке: инвентарь слева, активное устройство в центре,
            раскатка, observer, реестр модулей и конструктор форм в едином операционном интерфейсе.
          </p>
        </div>

        <dl className="workspace-page__stats">
          <div>
            <dt>Всего в инвентаре</dt>
            <dd>{summary.visible_count}</dd>
          </div>
          <div>
            <dt>Онлайн сейчас</dt>
            <dd>{summary.online_count}</dd>
          </div>
          <div>
            <dt>Rollout targets</dt>
            <dd>{summary.rollout_targets}</dd>
          </div>
        </dl>
      </header>

      <section className="admin-workspace__grid">
        <article className="support-workspace__panel">
          <div className="support-workspace__panel-head">
            <div>
              <h2>Инвентарь устройств</h2>
              <p>Проверяем состав парка, связь агентов и готовность к rollout без возврата в legacy admin shell.</p>
            </div>
          </div>

          <div className="support-queue-toolbar">
            <label className="support-filter-search">
              <span>Поиск по инвентарю</span>
              <input
                onChange={(event) => {
                  const value = event.currentTarget.value;
                  startTransition(() => {
                    setQueryDraft(value);
                  });
                }}
                placeholder="device_id, hostname, ОС или версия"
                type="search"
                value={queryDraft}
              />
            </label>

            <label className="support-filter-select">
              <span>Срез по связи</span>
              <select
                onChange={(event) => {
                  const value = event.currentTarget.value as AdminStatusFilter;
                  startTransition(() => {
                    setStatusFilter(value);
                  });
                }}
                value={statusFilter}
              >
                {filters.status_options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="support-queue-summary">
            <span>Устройств в текущем срезе: {devices.length}</span>
            <span>Активные возможности: {bootstrap.features.join(" · ")}</span>
          </div>

          <section className="admin-rollout">
            <div className="support-ticket-detail__section-head">
              <h3>Назначения rollout</h3>
              <span>{rollout.length}</span>
            </div>
            {rollout.length ? (
              <div className="admin-rollout__list">
                {rollout.map((item) => (
                  <article key={`${item.target}:${item.channel}:${item.version}`} className="workspace-card">
                    <p className="workspace-card__code">{item.target}</p>
                    <h3>
                      {item.channel}/{item.version}
                    </h3>
                    <p>{item.updated_by ? `Обновил ${item.updated_by}` : "Источник обновления не указан"}</p>
                    <p>Изменено: {formatDateTime(item.updated_at)}</p>
                  </article>
                ))}
              </div>
            ) : (
              <div className="support-queue-empty">Назначений rollout пока нет. Новый boundary уже готов их показывать.</div>
            )}
          </section>

          {devices.length ? (
            <div className="admin-device-list">
              {devices.map((device) => (
                <button
                  className={`support-ticket-card admin-device-card${selectedDevice?.device_id === device.device_id ? " active" : ""}`}
                  key={device.device_id}
                  onClick={() => {
                    startTransition(() => {
                      setSelectedDeviceId(device.device_id);
                    });
                  }}
                  type="button"
                >
                  <div className="support-ticket-card__head">
                    <strong>{device.hostname ?? device.device_id}</strong>
                    <span className="support-ticket-card__status">{device.connection_status_label}</span>
                  </div>
                  <p>{device.os ?? "ОС не определена"}</p>
                  <div className="support-ticket-card__meta">
                    <span>{device.target ?? "Платформа не определена"}</span>
                    <span>{device.agent_version ?? "Версия не указана"}</span>
                    <span>{formatDateTime(device.last_seen_at)}</span>
                  </div>
                  <p>{device.latest_update.summary ?? "Нет свежих данных по rollout."}</p>
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
            <div>
              <h2>Карточка устройства</h2>
              <p>Операционный обзор устройства, update flow и observer quick panel в том же стиле, что и support.</p>
            </div>
          </div>

          {selectedDevice ? (
            <section className="admin-device-detail">
              <header className="support-ticket-layout__header support-ticket-layout__header--compact">
                <div className="support-ticket-layout__title">
                  <p className="support-ticket-detail__code">{selectedDevice.device_id}</p>
                  <h2>{selectedDevice.hostname ?? "Имя узла не указано"}</h2>
                  <div className="support-ticket-layout__meta">
                    <span>{selectedDevice.os ?? "ОС не определена"}</span>
                    <span>Target: {selectedDevice.target ?? "—"}</span>
                    <span>Последний контакт: {formatDateTime(selectedDevice.last_seen_at)}</span>
                  </div>
                </div>
                <div className="support-ticket-layout__actions">
                  <div className="support-ticket-layout__status-pill">{selectedDevice.connection_status_label}</div>
                </div>
              </header>

              <div className="support-snapshot-grid">
                <article className="support-snapshot-card">
                  <span>Версия агента</span>
                  <strong>{selectedDevice.agent_version ?? "Неизвестно"}</strong>
                  <p>Срез нужен для rollout-решений и контроля расхождений по парку устройств.</p>
                </article>
                <article className="support-snapshot-card">
                  <span>Готовность к обновлению</span>
                  <strong>{selectedDevice.latest_update.label}</strong>
                  <p>{selectedDevice.latest_update.summary ?? "Нет свежих данных по update workflow."}</p>
                </article>
                <article className="support-snapshot-card">
                  <span>Эндпоинт observer</span>
                  <strong>{bootstrap.observer.quick_endpoint}</strong>
                  <p>Тот же shell показывает быстрый trace-срез и drilldown без legacy tech panel.</p>
                </article>
              </div>

              <ObserverQuickPanel
                deviceId={selectedDevice.device_id}
                deviceLabel={selectedDevice.hostname ?? selectedDevice.device_id}
              />
            </section>
          ) : (
            <div className="support-ticket-empty">Выберите устройство слева, чтобы открыть карточку деталей.</div>
          )}
        </article>
      </section>

      <ModulesPanel />
      <FormsBuilderPanel />
    </section>
  );
}
