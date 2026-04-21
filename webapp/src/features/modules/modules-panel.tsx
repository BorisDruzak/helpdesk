import { startTransition, useDeferredValue, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type AdminModulesRolloutSettings,
  fetchAdminModules,
  patchAdminModulesRolloutSettings,
  setAdminModulePreferredVersion
} from "./api";


type ActionFeedback =
  | {
      tone: "success" | "error";
      text: string;
    }
  | null;


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


function formatRolloutSyncLabel(value: boolean): string {
  return value ? "После смены preferred запускаем sync" : "Sync запускается вручную";
}


function getRolloutModeLabel(value: string): string {
  if (value === "installed_devices") {
    return "Обновлять установленные устройства";
  }
  return "Только вручную";
}


export function ModulesPanel() {
  const queryClient = useQueryClient();
  const [queryDraft, setQueryDraft] = useState("");
  const [selectedModuleName, setSelectedModuleName] = useState<string | null>(null);
  const [rolloutModeDraft, setRolloutModeDraft] = useState("manual");
  const [syncAfterPreferredDraft, setSyncAfterPreferredDraft] = useState(true);
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback>(null);
  const deferredQuery = useDeferredValue(queryDraft);

  const modulesQuery = useQuery({
    queryKey: ["admin-modules", deferredQuery],
    queryFn: () =>
      fetchAdminModules({
        query: deferredQuery
      }),
    retry: false
  });

  const modules = modulesQuery.data?.modules ?? [];
  const selectedModule =
    modules.find((item) => item.module_name === selectedModuleName) ?? modules[0] ?? null;

  useEffect(() => {
    if (!modules.length) {
      if (selectedModuleName !== null) {
        setSelectedModuleName(null);
      }
      return;
    }

    if (!selectedModuleName || !modules.some((item) => item.module_name === selectedModuleName)) {
      setSelectedModuleName(modules[0].module_name);
    }
  }, [modules, selectedModuleName]);

  useEffect(() => {
    const settings = modulesQuery.data?.rollout_settings;
    if (!settings) {
      return;
    }
    setRolloutModeDraft(settings.preferred_version_rollout_mode);
    setSyncAfterPreferredDraft(settings.sync_after_preferred_change);
  }, [modulesQuery.data?.rollout_settings]);

  const rolloutMutation = useMutation({
    mutationFn: patchAdminModulesRolloutSettings,
    onSuccess: async (settings: AdminModulesRolloutSettings) => {
      setActionFeedback({
        tone: "success",
        text: `Политика раскатки сохранена: ${settings.preferred_version_rollout_mode_label}.`
      });
      setRolloutModeDraft(settings.preferred_version_rollout_mode);
      setSyncAfterPreferredDraft(settings.sync_after_preferred_change);
      await queryClient.invalidateQueries({ queryKey: ["admin-modules"] });
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось сохранить rollout policy модулей."
      });
    }
  });

  const preferredMutation = useMutation({
    mutationFn: setAdminModulePreferredVersion,
    onSuccess: async (payload) => {
      setActionFeedback({
        tone: "success",
        text: payload.message
      });
      await queryClient.invalidateQueries({ queryKey: ["admin-modules"] });
    },
    onError: (error) => {
      setActionFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось обновить preferred-версию модуля."
      });
    }
  });

  const rolloutSettings = modulesQuery.data?.rollout_settings ?? null;
  const rolloutDraftChanged =
    rolloutSettings !== null &&
    (rolloutSettings.preferred_version_rollout_mode !== rolloutModeDraft ||
      rolloutSettings.sync_after_preferred_change !== syncAfterPreferredDraft);

  return (
    <section className="support-workspace__panel admin-modules-panel">
      <div className="support-workspace__panel-head">
        <div>
          <h2>Реестр модулей</h2>
          <p>
            Переносим модульный workbench в typed boundary: здесь уже видны семейства модулей,
            preferred-version policy и статус артефактов без legacy admin modules shell.
          </p>
        </div>
      </div>

      <div className="support-filters admin-filters">
        <label className="support-filter-search">
          <span>Поиск по registry</span>
          <input
            type="search"
            value={queryDraft}
            onChange={(event) => {
              const value = event.currentTarget.value;
              startTransition(() => {
                setQueryDraft(value);
              });
            }}
            placeholder="module_name, tool id или версия"
          />
        </label>
      </div>

      {modulesQuery.isLoading ? (
        <div className="support-detail-note">
          Собираем семейства модулей, rollout policy и preferred-version назначения…
        </div>
      ) : null}

      {modulesQuery.isError ? (
        <div className="support-detail-error">
          {modulesQuery.error instanceof Error
            ? modulesQuery.error.message
            : "Не удалось загрузить реестр модулей."}
        </div>
      ) : null}

      {actionFeedback ? (
        <div className={actionFeedback.tone === "success" ? "support-detail-note" : "support-detail-error"}>
          {actionFeedback.text}
        </div>
      ) : null}

      {modulesQuery.data ? (
        <>
          <div className="support-snapshot-grid">
            <article className="support-snapshot-card">
              <span>Семейств в срезе</span>
              <strong>{modulesQuery.data.summary.visible_count}</strong>
              <p>Preferred-version назначений: {modulesQuery.data.summary.preferred_count}</p>
            </article>
            <article className="support-snapshot-card">
              <span>С предупреждениями</span>
              <strong>{modulesQuery.data.summary.invalid_count}</strong>
              <p>Архивов отсутствует: {modulesQuery.data.summary.missing_files_count}</p>
            </article>
            <article className="support-snapshot-card">
              <span>Rollout policy</span>
              <strong>{modulesQuery.data.rollout_settings.preferred_version_rollout_mode_label}</strong>
              <p>{formatRolloutSyncLabel(modulesQuery.data.rollout_settings.sync_after_preferred_change)}</p>
            </article>
          </div>

          <section className="admin-modules-controls">
            <label className="support-filter-select">
              <span>Режим preferred-rollout</span>
              <select
                aria-label="Режим preferred-rollout"
                value={rolloutModeDraft}
                onChange={(event) => {
                  setActionFeedback(null);
                  setRolloutModeDraft(event.currentTarget.value);
                }}
                disabled={rolloutMutation.isPending}
              >
                <option value="manual">Только вручную</option>
                <option value="installed_devices">Обновлять установленные устройства</option>
              </select>
            </label>

            <label className="admin-modules-toggle">
              <input
                type="checkbox"
                checked={syncAfterPreferredDraft}
                onChange={(event) => {
                  setActionFeedback(null);
                  setSyncAfterPreferredDraft(event.currentTarget.checked);
                }}
                disabled={rolloutMutation.isPending}
              />
              <span>После смены preferred запускать sync и refresh</span>
            </label>

            <button
              type="button"
              className="admin-modules-action"
              disabled={!rolloutDraftChanged || rolloutMutation.isPending}
              onClick={() => {
                setActionFeedback(null);
                rolloutMutation.mutate({
                  preferred_version_rollout_mode: rolloutModeDraft,
                  sync_after_preferred_change: syncAfterPreferredDraft
                });
              }}
            >
              {rolloutMutation.isPending ? "Сохраняем…" : "Сохранить политику"}
            </button>
          </section>

          <div className="admin-modules-grid">
            <article className="support-operation-card">
              <div className="support-operations__head">
                <strong>Семейства модулей</strong>
                <span>{modules.length}</span>
              </div>
              {modules.length ? (
                <div className="admin-modules-list">
                  {modules.map((moduleFamily) => (
                    <button
                      key={moduleFamily.module_name}
                      type="button"
                      className={`admin-module-card${selectedModule?.module_name === moduleFamily.module_name ? " active" : ""}`}
                      onClick={() => {
                        setActionFeedback(null);
                        startTransition(() => {
                          setSelectedModuleName(moduleFamily.module_name);
                        });
                      }}
                    >
                      <div className="admin-observer-item__head">
                        <strong>{moduleFamily.module_name}</strong>
                        <span>{moduleFamily.validation_status_label}</span>
                      </div>
                      <p>
                        Preferred: {moduleFamily.preferred_version ?? "не назначен"} · latest:{" "}
                        {moduleFamily.latest_version ?? "нет данных"}
                      </p>
                      <p>
                        Инструментов: {moduleFamily.tools_count} · версий: {moduleFamily.version_count}
                      </p>
                      <p>
                        {moduleFamily.has_missing_files
                          ? "Есть missing archive в registry"
                          : "Архивы для family доступны на сервере"}
                      </p>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="support-queue-empty">
                  Под текущий поиск модулей пока ничего не найдено.
                </div>
              )}
            </article>

            <article className="support-operation-card">
              <div className="support-operations__head">
                <strong>Карточка семейства</strong>
                <span>{selectedModule?.module_name ?? "Нет выбора"}</span>
              </div>

              {selectedModule ? (
                <div className="admin-modules-detail">
                  <div className="support-snapshot-grid">
                    <article className="support-snapshot-card">
                      <span>Предпочтительная версия</span>
                      <strong>{selectedModule.preferred_version ?? "Не назначена"}</strong>
                      <p>Latest: {selectedModule.latest_version ?? "Нет данных"}</p>
                    </article>
                    <article className="support-snapshot-card">
                      <span>Owner scope</span>
                      <strong>{selectedModule.owner_scope ?? "Не указан"}</strong>
                      <p>Module API: {selectedModule.module_api_version ?? "Не указана"}</p>
                    </article>
                    <article className="support-snapshot-card">
                      <span>Инструменты</span>
                      <strong>{selectedModule.tools_count}</strong>
                      <p>{selectedModule.tool_ids.join(", ") || "Инструменты не заявлены"}</p>
                    </article>
                  </div>

                  <div className="admin-modules-detail__meta">
                    <div>
                      <span>Платформы</span>
                      <strong>{selectedModule.platforms.join(", ") || "any"}</strong>
                    </div>
                    <div>
                      <span>Статус family</span>
                      <strong>{selectedModule.validation_status_label}</strong>
                    </div>
                    <div>
                      <span>Warnings</span>
                      <strong>{selectedModule.warnings_count}</strong>
                    </div>
                  </div>

                  <div className="admin-modules-detail__actions">
                    <button
                      type="button"
                      className="admin-modules-action"
                      disabled={!selectedModule.preferred_assigned || preferredMutation.isPending}
                      onClick={() => {
                        setActionFeedback(null);
                        preferredMutation.mutate({
                          moduleName: selectedModule.module_name,
                          version: null
                        });
                      }}
                    >
                      {preferredMutation.isPending && selectedModule.preferred_assigned
                        ? "Обновляем preferred…"
                        : "Снять preferred"}
                    </button>
                    <span className="admin-modules-detail__hint">
                      Текущий режим: {getRolloutModeLabel(rolloutModeDraft)}
                    </span>
                  </div>

                  <section className="admin-modules-versions">
                    <div className="support-operations__head">
                      <strong>Версии в registry</strong>
                      <span>{selectedModule.versions.length}</span>
                    </div>
                    <div className="admin-modules-version-list">
                      {selectedModule.versions.map((version) => {
                        const actionLabel = version.is_preferred
                          ? "Снять preferred"
                          : `Сделать preferred для ${version.version}`;
                        const actionDisabled = preferredMutation.isPending || (!version.is_preferred && !version.file_exists);
                        return (
                          <article key={`${selectedModule.module_name}:${version.version}`} className="admin-modules-version-card">
                            <div className="admin-observer-item__head">
                              <strong>{version.version}</strong>
                              <span>{version.is_preferred ? "preferred" : version.validation_status_label}</span>
                            </div>
                            <p>
                              Preflight: {version.preflight_status_label} · tools: {version.tools_count}
                            </p>
                            <p>{version.platforms.join(", ") || "any"}</p>
                            <p>
                              {version.file_exists
                                ? "Архив доступен на сервере"
                                : "Архив отсутствует, нужен повторный upload"}
                            </p>
                            <p>Опубликован: {formatDateTime(version.created_at)}</p>
                            <button
                              type="button"
                              className="admin-modules-action"
                              disabled={actionDisabled}
                              onClick={() => {
                                setActionFeedback(null);
                                preferredMutation.mutate({
                                  moduleName: selectedModule.module_name,
                                  version: version.is_preferred ? null : version.version
                                });
                              }}
                            >
                              {preferredMutation.isPending ? "Обновляем preferred…" : actionLabel}
                            </button>
                          </article>
                        );
                      })}
                    </div>
                  </section>
                </div>
              ) : (
                <div className="support-queue-empty">
                  Выберите семейство слева, чтобы открыть детали registry и preferred-version policy.
                </div>
              )}
            </article>
          </div>
        </>
      ) : null}
    </section>
  );
}
