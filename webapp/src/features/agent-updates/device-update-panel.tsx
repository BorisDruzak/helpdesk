import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { fetchAdminDeviceUpdates, runAdminDeviceUpdate } from "./api";


type DeviceSummary = {
  device_id: string;
  hostname: string | null;
};

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

function buildBuildLabel(build: { channel: string; version: string } | null | undefined): string {
  if (!build) {
    return "Не назначена";
  }
  return `${build.channel}/${build.version}`;
}

export function DeviceUpdatePanel({ device }: { device: DeviceSummary | null }) {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const updatesQuery = useQuery({
    queryKey: ["admin-device-updates", device?.device_id],
    queryFn: () => fetchAdminDeviceUpdates(device!.device_id),
    enabled: Boolean(device?.device_id),
    retry: false
  });

  const runUpdateMutation = useMutation({
    mutationFn: async () =>
      runAdminDeviceUpdate(device!.device_id, {
        reason: reason.trim()
      }),
    onSuccess: async (payload) => {
      setActionMessage(payload.message);
      await queryClient.invalidateQueries({
        queryKey: ["admin-device-updates", device?.device_id]
      });
    }
  });

  useEffect(() => {
    setReason("");
    setActionMessage(null);
  }, [device?.device_id]);

  if (!device) {
    return null;
  }

  if (updatesQuery.isLoading) {
    return (
      <section className="admin-update-panel">
        <div className="support-workspace__panel-head">
          <h3>Обновление агента</h3>
          <span>Собираем rollout-контекст…</span>
        </div>
      </section>
    );
  }

  if (updatesQuery.isError || !updatesQuery.data) {
    return (
      <section className="admin-update-panel">
        <div className="support-workspace__panel-head">
          <h3>Обновление агента</h3>
          <span>Не удалось загрузить сценарий обновления</span>
        </div>
      </section>
    );
  }

  const updates = updatesQuery.data;
  const recommendedBuild = updates.recommendation.recommended_build;
  const assignedRollout = updates.recommendation.assigned_rollout;
  const canRun = updates.action.enabled && reason.trim().length > 0 && !runUpdateMutation.isPending;

  return (
    <section className="admin-update-panel">
      <div className="support-workspace__panel-head">
        <h3>Обновление агента</h3>
        <span>{updates.summary.label}</span>
      </div>

      <div className="support-ticket-detail__grid">
        <article className="support-snapshot-card">
          <span>Текущая версия</span>
          <strong>{updates.current_version ?? "Неизвестно"}</strong>
          <p>{updates.summary.summary ?? "Сервер ещё не сформировал рекомендацию для устройства."}</p>
        </article>
        <article className="support-snapshot-card">
          <span>Target агента</span>
          <strong>{updates.target ?? "не определён"}</strong>
          <p>{updates.target?.startsWith("linux") ? "Linux агент обновляется через тот же rollout workflow." : "Платформа определена из профиля устройства."}</p>
        </article>
        <article className="support-snapshot-card">
          <span>Рекомендуемая сборка</span>
          <strong>{recommendedBuild ? "Доступна" : "Не назначена"}</strong>
          <p>
            {recommendedBuild
              ? `${updates.recommendation.comparison_label}: ${recommendedBuild.channel} / ${recommendedBuild.version}`
              : updates.recommendation.comparison_label}
          </p>
        </article>
        <article className="support-snapshot-card">
          <span>Назначенный rollout</span>
          <strong>{buildBuildLabel(assignedRollout)}</strong>
          <p>
            {assignedRollout?.updated_at
              ? `Обновлено ${formatDateTime(assignedRollout.updated_at)}`
              : "Политика rollout для платформы пока не назначена."}
          </p>
        </article>
      </div>

      <div className="admin-update-panel__meta">
        <span>Источник рекомендации: {updates.recommendation.recommendation_source_label}</span>
        <span>Платформа: {updates.target ?? "не определена"}</span>
        <span>Канал текущей версии: {updates.release_channel}</span>
      </div>

      {updates.recommendation.recommended_reason_label ? (
        <p className="admin-update-panel__hint">{updates.recommendation.recommended_reason_label}</p>
      ) : null}
      {actionMessage ? <p className="admin-update-panel__status">{actionMessage}</p> : null}
      {runUpdateMutation.isError ? (
        <p className="admin-update-panel__error">
          {runUpdateMutation.error instanceof Error
            ? runUpdateMutation.error.message
            : "Не удалось поставить обновление в очередь."}
        </p>
      ) : null}

      <form
        className="admin-update-form"
        onSubmit={(event) => {
          event.preventDefault();
          if (!canRun) {
            return;
          }
          runUpdateMutation.mutate();
        }}
      >
        <label className="support-filter-search admin-update-form__field">
          <span>Причина запуска</span>
          <textarea
            onChange={(event) => setReason(event.currentTarget.value)}
            placeholder="Например: canary после smoke, перед массовой раскаткой."
            rows={3}
            value={reason}
          />
        </label>
        <button
          className="auth-form__submit admin-update-form__submit"
          disabled={!canRun}
          type="submit"
        >
          {runUpdateMutation.isPending ? "Ставим в очередь…" : updates.action.label}
        </button>
      </form>
    </section>
  );
}
