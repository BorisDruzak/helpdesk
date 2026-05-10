import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Monitor, ShieldCheck, X } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import {
  fetchRemoteAssistSessions,
  requestRemoteAssist,
  type RemoteAssistMediaOptions,
  type RemoteAssistSession,
} from "./api";
import { RemoteAssistViewer } from "./remote-assist-viewer";

function statusLabel(status: string, consentStatus: string) {
  if (status === "waiting_consent") {
    return "Ожидаем подтверждения пользователя";
  }
  if (status === "approved") {
    return "Пользователь разрешил доступ";
  }
  if (status === "denied" || consentStatus === "denied") {
    return "Пользователь отклонил запрос";
  }
  if (status === "expired") {
    return "Запрос истёк";
  }
  if (status === "failed") {
    return "Ошибка удалённой помощи";
  }
  if (status === "active") {
    return "Сессия активна";
  }
  if (status === "ended") {
    return "Сессия завершена";
  }
  return status || "Нет активной сессии";
}

function statusTone(status: string) {
  if (status === "approved" || status === "active") {
    return "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
  }
  if (status === "waiting_consent") {
    return "border-amber-400/30 bg-amber-500/10 text-amber-100";
  }
  if (status === "failed" || status === "denied" || status === "expired") {
    return "border-rose-400/30 bg-rose-500/10 text-rose-100";
  }
  return "border-white/10 bg-white/[0.04] text-slate-300";
}

const QUALITY_PRESETS: Record<string, RemoteAssistMediaOptions & { label: string; description: string }> = {
  balanced: {
    label: "Сбалансированное",
    description: "1600x900, 8 fps",
    quality_profile: "balanced",
    max_width: 1600,
    max_height: 900,
    fps: 8,
    monitor_id: "primary",
  },
  smooth: {
    label: "Плавное",
    description: "1280x720, 15 fps",
    quality_profile: "smooth",
    max_width: 1280,
    max_height: 720,
    fps: 15,
    monitor_id: "primary",
  },
  sharp: {
    label: "Чёткое",
    description: "1920x1080, 12 fps",
    quality_profile: "sharp",
    max_width: 1920,
    max_height: 1080,
    fps: 12,
    monitor_id: "primary",
  },
  fast: {
    label: "Быстрое",
    description: "1024x576, 5 fps",
    quality_profile: "fast",
    max_width: 1024,
    max_height: 576,
    fps: 5,
    monitor_id: "primary",
  },
};

type RemoteAssistPanelProps = {
  ticketId: string;
  deviceId: string | null;
  deviceOnline: boolean;
  permissions?: string[];
  onChanged?: () => void;
};

export function buildRemoteAssistFeatureOptions(requestedMode: string, clipboardAutoSync: boolean) {
  return {
    clipboard_auto_sync: requestedMode === "interactive_control" && clipboardAutoSync,
  };
}

export function RemoteAssistPanel({ ticketId, deviceId, deviceOnline, permissions = [], onChanged }: RemoteAssistPanelProps) {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [viewerSessionId, setViewerSessionId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(15);
  const [mode, setMode] = useState("view_only");
  const [qualityProfile, setQualityProfile] = useState("smooth");
  const [clipboardAutoSync, setClipboardAutoSync] = useState(false);
  const modeRef = useRef(mode);
  const qualityProfileRef = useRef(qualityProfile);
  const clipboardAutoSyncRef = useRef(clipboardAutoSync);

  const sessionsQuery = useQuery({
    queryKey: ["remote-assist", ticketId],
    queryFn: () => fetchRemoteAssistSessions(ticketId),
    enabled: Boolean(ticketId),
    retry: false,
    refetchInterval: (query) => {
      const latest = query.state.data?.[0];
      return latest && ["waiting_consent", "approved", "starting", "active"].includes(latest.status) ? 5000 : false;
    },
  });

  const latestSession = useMemo<RemoteAssistSession | null>(() => sessionsQuery.data?.[0] ?? null, [sessionsQuery.data]);
  const activeOrWaiting = latestSession && ["waiting_consent", "approved", "starting", "active"].includes(latestSession.status);
  const reasonReady = reason.trim().length >= 3;
  const hasClipboardPermission = permissions.includes("remote_assist.clipboard");

  const requestMutation = useMutation({
    mutationFn: () => {
      if (!deviceId) {
        throw new Error("Устройство для тикета не указано.");
      }
      const requestedMode = modeRef.current;
      const requestedClipboard = requestedMode === "interactive_control" && clipboardAutoSyncRef.current && hasClipboardPermission;
      return requestRemoteAssist(ticketId, {
        deviceId,
        mode: requestedMode,
        reason: reason.trim(),
        durationMinutes,
        media: QUALITY_PRESETS[qualityProfileRef.current] ?? QUALITY_PRESETS.balanced,
        features: buildRemoteAssistFeatureOptions(requestedMode, requestedClipboard),
      });
    },
    onSuccess: () => {
      setModalOpen(false);
      setReason("");
      setMode("view_only");
      modeRef.current = "view_only";
      setQualityProfile("smooth");
      qualityProfileRef.current = "smooth";
      setClipboardAutoSync(false);
      clipboardAutoSyncRef.current = false;
      void queryClient.invalidateQueries({ queryKey: ["remote-assist", ticketId] });
      onChanged?.();
    },
  });

  const disabledReason = !deviceId
    ? "К тикету не привязано устройство."
    : !deviceOnline
      ? "Устройство сейчас недоступно."
      : activeOrWaiting
        ? "По этому тикету уже есть активный или ожидающий запрос."
        : null;

  return (
    <section className="rounded-xl border border-white/10 bg-[#111f33] p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Monitor className="h-4 w-4 text-blue-200" />
            <p className="font-semibold text-white">Удалённая помощь</p>
          </div>
          <p className="mt-1 text-xs text-slate-400">Только просмотр экрана, с обязательным согласием пользователя.</p>
        </div>
        <button
          className="shrink-0 rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
          disabled={Boolean(disabledReason) || requestMutation.isPending}
          onClick={() => setModalOpen(true)}
          title={disabledReason ?? "Запросить удалённую помощь"}
          type="button"
        >
          Запросить
        </button>
      </div>

      {latestSession ? (
        <div className={`mt-3 rounded-xl border px-3 py-2 text-sm ${statusTone(latestSession.status)}`}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" />
              <span className="font-semibold">{statusLabel(latestSession.status, latestSession.consent_status)}</span>
            </div>
            {["approved", "starting", "active"].includes(latestSession.status) ? (
              <button
                className="rounded-lg border border-white/10 px-2.5 py-1 text-xs font-semibold text-white hover:bg-white/10"
                onClick={() => setViewerSessionId(latestSession.session_id)}
                type="button"
              >
                Открыть
              </button>
            ) : null}
          </div>
          {latestSession.reason ? <p className="mt-1 text-xs opacity-80">{latestSession.reason}</p> : null}
        </div>
      ) : (
        <p className="mt-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-slate-400">
          Сессий удалённой помощи по тикету пока нет.
        </p>
      )}

      {disabledReason && !activeOrWaiting ? <p className="mt-2 text-xs text-amber-200">{disabledReason}</p> : null}
      {requestMutation.isError ? (
        <p className="mt-2 text-xs text-rose-200">
          {requestMutation.error instanceof Error ? requestMutation.error.message : "Не удалось запросить удалённую помощь."}
        </p>
      ) : null}

      {modalOpen ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm" role="presentation">
          <section
            aria-labelledby="remote-assist-title"
            aria-modal="true"
            className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#101d30] p-5 text-slate-100 shadow-2xl shadow-black/50"
            role="dialog"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold" id="remote-assist-title">Запрос удалённой помощи</h2>
                <p className="mt-1 text-sm leading-6 text-slate-400">Режим управления доступен только при включённой server policy и требует согласия пользователя.</p>
              </div>
              <button
                aria-label="Закрыть"
                className="rounded-lg border border-white/10 p-2 text-slate-300 hover:text-white"
                onClick={() => setModalOpen(false)}
                type="button"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-5 space-y-4">
              <label className="block text-sm font-medium text-slate-300">
                Режим
                <select
                  className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none"
                  onChange={(event) => {
                    const nextMode = event.currentTarget.value;
                    modeRef.current = nextMode;
                    setMode(nextMode);
                    if (nextMode !== "interactive_control") {
                      clipboardAutoSyncRef.current = false;
                      setClipboardAutoSync(false);
                    }
                  }}
                  value={mode}
                >
                  <option value="view_only">Только просмотр</option>
                  <option value="interactive_control">Просмотр и управление</option>
                  <option value="file_transfer" disabled>
                    Передача файлов (policy gate)
                  </option>
                  <option value="elevated_admin" disabled>
                    Admin mode (policy gate)
                  </option>
                </select>
              </label>
              {mode === "interactive_control" ? (
                <label className="flex items-start gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-sm text-slate-300">
                  <input
                    checked={clipboardAutoSync}
                    className="mt-1"
                    disabled={!hasClipboardPermission}
                    onChange={(event) => {
                      clipboardAutoSyncRef.current = event.currentTarget.checked;
                      setClipboardAutoSync(event.currentTarget.checked);
                    }}
                    type="checkbox"
                  />
                  <span>
                    <span className="block font-semibold text-slate-100">Автосинхронизация буфера обмена</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-400">
                      Текстовый буфер обмена будет синхронизироваться между оператором и устройством во время сессии.
                    </span>
                  </span>
                </label>
              ) : null}
              <label className="block text-sm font-medium text-slate-300">
                Качество видео
                <select
                  className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none"
                  onChange={(event) => {
                    qualityProfileRef.current = event.currentTarget.value;
                    setQualityProfile(event.currentTarget.value);
                  }}
                  value={qualityProfile}
                >
                  {Object.entries(QUALITY_PRESETS).map(([value, preset]) => (
                    <option key={value} value={value}>
                      {preset.label} - {preset.description}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium text-slate-300">
                Причина
                <textarea
                  className="mt-2 min-h-24 w-full resize-none rounded-xl border border-white/10 bg-[#0d1828] px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-600"
                  onChange={(event) => setReason(event.currentTarget.value)}
                  placeholder="Например: проверить ошибку сайта вместе с пользователем"
                  value={reason}
                />
              </label>
              <label className="block text-sm font-medium text-slate-300">
                Длительность
                <select
                  className="mt-2 h-11 w-full rounded-xl border border-white/10 bg-[#0d1828] px-3 text-sm text-slate-100 outline-none"
                  onChange={(event) => setDurationMinutes(Number(event.currentTarget.value))}
                  value={durationMinutes}
                >
                  <option value={15}>15 минут</option>
                  <option value={30}>30 минут</option>
                </select>
              </label>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                className="h-10 rounded-xl border border-white/10 px-4 text-sm font-semibold text-slate-300 hover:text-white"
                onClick={() => setModalOpen(false)}
                type="button"
              >
                Отмена
              </button>
              <button
                className="h-10 rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={!reasonReady || requestMutation.isPending}
                onClick={() => requestMutation.mutate()}
                type="button"
              >
                {requestMutation.isPending ? "Отправляем..." : "Отправить запрос"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
      {viewerSessionId ? (
        <RemoteAssistViewer
          onClose={() => setViewerSessionId(null)}
          onEnded={() => {
            setViewerSessionId(null);
            void queryClient.invalidateQueries({ queryKey: ["remote-assist", ticketId] });
            onChanged?.();
          }}
          sessionId={viewerSessionId}
        />
      ) : null}
    </section>
  );
}
