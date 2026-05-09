import {
  CheckCircle2,
  Download,
  RefreshCcw,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDeferredValue, useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { SearchField } from "../../components/ui/search-field";
import { Select } from "../../components/ui/select";
import { cn } from "../../shared/ui/cn";
import {
  clearAgentRolloutPolicy,
  deleteAgentBuild,
  fetchAdminDeviceUpdates,
  fetchAgentBuilds,
  fetchAgentRolloutPolicy,
  setAgentRolloutPolicy,
  uploadAgentBuild,
  type AgentBuildItem,
  type AgentRolloutAssignment,
} from "./api";

type AgentUpdatesPanelProps = {
  deviceId?: string | null;
  initialTarget?: string | null;
};

type BuildUploadDraft = {
  archiveType: "zip" | "tar.gz";
  channel: string;
  file: File | null;
  notes: string;
  target: string;
  version: string;
};

const DEFAULT_UPLOAD_DRAFT: BuildUploadDraft = {
  archiveType: "zip",
  channel: "stable",
  file: null,
  notes: "",
  target: "windows_amd64",
  version: "",
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
    timeStyle: "short",
  }).format(date);
}

function formatBytes(value: number | null | undefined): string {
  const size = Number(value ?? 0);
  if (!Number.isFinite(size) || size <= 0) {
    return "0 Б";
  }
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let current = size;
  let unitIndex = 0;
  while (current >= 1024 && unitIndex < units.length - 1) {
    current /= 1024;
    unitIndex += 1;
  }
  return `${current.toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function compactHash(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  return value.length > 14 ? `${value.slice(0, 10)}…${value.slice(-4)}` : value;
}

function buildKey(build: Pick<AgentBuildItem, "target" | "channel" | "version">): string {
  return `${build.target}:${build.channel}:${build.version}`;
}

function buildLabel(build: Pick<AgentBuildItem, "target" | "channel" | "version">): string {
  return `${build.target} / ${build.channel} / ${build.version}`;
}

function sortBuilds(builds: AgentBuildItem[]): AgentBuildItem[] {
  return [...builds].sort((left, right) => {
    const targetCompare = left.target.localeCompare(right.target);
    if (targetCompare !== 0) {
      return targetCompare;
    }
    const dateCompare = String(right.created_at ?? "").localeCompare(String(left.created_at ?? ""));
    if (dateCompare !== 0) {
      return dateCompare;
    }
    return right.version.localeCompare(left.version, undefined, { numeric: true, sensitivity: "base" });
  });
}

function assignmentLabel(assignment: AgentRolloutAssignment | null | undefined): string {
  if (!assignment) {
    return "Не назначен";
  }
  return `${assignment.channel}/${assignment.version}`;
}

function matchesQuery(build: AgentBuildItem, query: string): boolean {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  return [
    build.target,
    build.channel,
    build.version,
    build.artifact_filename,
    build.notes ?? "",
    build.sha256,
  ]
    .join(" ")
    .toLowerCase()
    .includes(normalized);
}

function findAssignment(assignments: AgentRolloutAssignment[], target: string): AgentRolloutAssignment | null {
  return assignments.find((item) => item.target === target) ?? null;
}

function groupByTarget(builds: AgentBuildItem[]): Array<{ target: string; builds: AgentBuildItem[] }> {
  const grouped = new Map<string, AgentBuildItem[]>();
  for (const build of builds) {
    grouped.set(build.target, [...(grouped.get(build.target) ?? []), build]);
  }
  return Array.from(grouped.entries()).map(([target, items]) => ({ target, builds: sortBuilds(items) }));
}

function UpdateContextCard({ deviceId }: { deviceId: string | null | undefined }) {
  const deviceQuery = useQuery({
    queryKey: ["admin-device-updates", deviceId],
    queryFn: () => fetchAdminDeviceUpdates(deviceId!),
    enabled: Boolean(deviceId),
    retry: false,
    refetchInterval: 15_000,
  });

  if (!deviceId) {
    return null;
  }

  if (deviceQuery.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Контекст выбранного устройства</CardTitle>
          <CardDescription>Загружаем current/recommended update status…</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (deviceQuery.isError || !deviceQuery.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Контекст выбранного устройства</CardTitle>
          <CardDescription>
            {deviceQuery.error instanceof Error
              ? deviceQuery.error.message
              : "Не удалось загрузить update-контекст устройства."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const updates = deviceQuery.data;
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>{updates.device_label}</CardTitle>
            <CardDescription>Current version, target rollout, recommended и последний статус update.</CardDescription>
          </div>
          <Badge tone={updates.online ? "success" : "neutral"} withDot>
            {updates.online ? "Онлайн" : "Офлайн"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Current version</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">{updates.current_version ?? "Неизвестно"}</p>
          </div>
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Target rollout</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">
              {assignmentLabel(updates.recommendation.assigned_rollout)}
            </p>
          </div>
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Recommended</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">
              {updates.recommendation.recommended_build
                ? `${updates.recommendation.recommended_build.channel}/${updates.recommendation.recommended_build.version}`
                : "Не назначен"}
            </p>
          </div>
          <div className="rounded-[1rem] bg-surface-subtle px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Last update result</p>
            <p className="mt-2 text-lg font-semibold text-slate-950">{updates.summary.label}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function AgentUpdatesPanel({ deviceId, initialTarget }: AgentUpdatesPanelProps) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [targetFilter, setTargetFilter] = useState(initialTarget ?? "all");
  const [channelFilter, setChannelFilter] = useState("all");
  const [draft, setDraft] = useState<BuildUploadDraft>({
    ...DEFAULT_UPLOAD_DRAFT,
    target: initialTarget || DEFAULT_UPLOAD_DRAFT.target,
  });
  const [feedback, setFeedback] = useState<string | null>(null);
  const deferredQuery = useDeferredValue(query);

  const buildsQuery = useQuery({
    queryKey: ["agent-builds-registry"],
    queryFn: () => fetchAgentBuilds({ limit: 200 }),
    retry: false,
  });

  const rolloutQuery = useQuery({
    queryKey: ["agent-rollout-policy"],
    queryFn: fetchAgentRolloutPolicy,
    retry: false,
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!draft.file) {
        throw new Error("Выберите ZIP или tar.gz файл build-а.");
      }
      if (!draft.target.trim() || !draft.channel.trim() || !draft.version.trim()) {
        throw new Error("Target, channel и version обязательны.");
      }
      return uploadAgentBuild({
        archiveType: draft.archiveType,
        channel: draft.channel.trim(),
        file: draft.file,
        notes: draft.notes,
        target: draft.target.trim(),
        version: draft.version.trim(),
      });
    },
    onSuccess: async (result) => {
      setFeedback(`Build загружен: ${result.target}/${result.channel}/${result.version}.`);
      setDraft((current) => ({
        ...DEFAULT_UPLOAD_DRAFT,
        target: current.target,
        channel: current.channel,
      }));
      await queryClient.invalidateQueries({ queryKey: ["agent-builds-registry"] });
      await queryClient.invalidateQueries({ queryKey: ["agent-rollout-policy"] });
    },
    onError: (error) => {
      setFeedback(error instanceof Error ? error.message : "Не удалось загрузить build.");
    },
  });

  const assignMutation = useMutation({
    mutationFn: (build: AgentBuildItem) =>
      setAgentRolloutPolicy({
        target: build.target,
        channel: build.channel,
        version: build.version,
      }),
    onSuccess: async (result) => {
      setFeedback(`Rollout policy назначен: ${result.target} -> ${result.assignment.channel}/${result.assignment.version}.`);
      await queryClient.invalidateQueries({ queryKey: ["agent-builds-registry"] });
      await queryClient.invalidateQueries({ queryKey: ["agent-rollout-policy"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-device-updates"] });
    },
    onError: (error) => {
      setFeedback(error instanceof Error ? error.message : "Не удалось назначить rollout policy.");
    },
  });

  const clearMutation = useMutation({
    mutationFn: (target: string) => clearAgentRolloutPolicy(target),
    onSuccess: async (result) => {
      setFeedback(`Rollout policy снят: ${result.target}.`);
      await queryClient.invalidateQueries({ queryKey: ["agent-builds-registry"] });
      await queryClient.invalidateQueries({ queryKey: ["agent-rollout-policy"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-device-updates"] });
    },
    onError: (error) => {
      setFeedback(error instanceof Error ? error.message : "Не удалось снять rollout policy.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (build: AgentBuildItem) => deleteAgentBuild(build),
    onSuccess: async (result) => {
      setFeedback(`Build удалён: ${result.target}/${result.channel}/${result.version}.`);
      await queryClient.invalidateQueries({ queryKey: ["agent-builds-registry"] });
      await queryClient.invalidateQueries({ queryKey: ["agent-rollout-policy"] });
    },
    onError: (error) => {
      setFeedback(error instanceof Error ? error.message : "Не удалось удалить build.");
    },
  });

  const builds = buildsQuery.data?.builds ?? [];
  const assignments = rolloutQuery.data?.assignments ?? [];
  const targets = useMemo(
    () => Array.from(new Set([...builds.map((item) => item.target), ...(rolloutQuery.data?.available_targets ?? [])])).sort(),
    [builds, rolloutQuery.data?.available_targets]
  );
  const channels = useMemo(() => Array.from(new Set(builds.map((item) => item.channel))).sort(), [builds]);
  const visibleBuilds = useMemo(
    () =>
      sortBuilds(builds).filter((build) => {
        if (targetFilter !== "all" && build.target !== targetFilter) {
          return false;
        }
        if (channelFilter !== "all" && build.channel !== channelFilter) {
          return false;
        }
        return matchesQuery(build, deferredQuery);
      }),
    [builds, channelFilter, deferredQuery, targetFilter]
  );
  const groups = groupByTarget(visibleBuilds);
  const assignedCount = assignments.filter((item) => !item.build_missing).length;
  const stable33133 = builds.find(
    (item) => item.target === "windows_amd64" && item.channel === "stable" && item.version === "3.1.33"
  );
  const windowsAssignment = findAssignment(assignments, "windows_amd64");

  return (
    <div className="space-y-6">
      <UpdateContextCard deviceId={deviceId} />

      <div className="grid gap-4 md:grid-cols-4">
        <Card className="px-5 py-4">
          <p className="text-sm text-slate-500">Builds</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{builds.length}</p>
        </Card>
        <Card className="px-5 py-4">
          <p className="text-sm text-slate-500">Targets</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{targets.length}</p>
        </Card>
        <Card className="px-5 py-4">
          <p className="text-sm text-slate-500">Assigned rollout</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{assignedCount}</p>
        </Card>
        <Card className="px-5 py-4">
          <p className="text-sm text-slate-500">Windows preferred</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">
            {windowsAssignment ? `${windowsAssignment.channel}/${windowsAssignment.version}` : "Нет"}
          </p>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <CardTitle>Rollout policy</CardTitle>
              <CardDescription>
                Server-side preferred build по target. Именно это значение используется как recommended version.
              </CardDescription>
            </div>
            <Button
              disabled={buildsQuery.isFetching || rolloutQuery.isFetching}
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => {
                void buildsQuery.refetch();
                void rolloutQuery.refetch();
              }}
              size="sm"
              variant="outline"
            >
              Обновить
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {rolloutQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем rollout policy…</p> : null}
          {rolloutQuery.isError ? (
            <p className="text-sm text-rose-600">
              {rolloutQuery.error instanceof Error ? rolloutQuery.error.message : "Не удалось загрузить policy."}
            </p>
          ) : null}
          {assignments.length === 0 && !rolloutQuery.isLoading ? (
            <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-5 text-sm text-slate-500">
              Активных rollout assignments нет. Назначьте build из реестра ниже.
            </div>
          ) : null}
          <div className="grid gap-3 lg:grid-cols-2">
            {assignments.map((assignment) => (
              <div className="rounded-[1rem] border border-border bg-white px-4 py-4" key={assignment.target}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{assignment.target}</p>
                    <p className="mt-2 text-xl font-semibold text-slate-950">{assignment.channel}/{assignment.version}</p>
                    <p className="mt-1 text-sm text-slate-500">Обновлено: {formatDateTime(assignment.updated_at)}</p>
                  </div>
                  <Badge tone={assignment.build_missing ? "danger" : "success"} withDot>
                    {assignment.build_missing ? "Build missing" : "Assigned"}
                  </Badge>
                </div>
                <Button
                  className="mt-4"
                  disabled={clearMutation.isPending}
                  onClick={() => clearMutation.mutate(assignment.target)}
                  size="sm"
                  variant="outline"
                >
                  Снять policy
                </Button>
              </div>
            ))}
          </div>
          {stable33133 ? (
            <div className="flex flex-col gap-3 rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-900 md:flex-row md:items-center md:justify-between">
              <span>
                Найден Windows stable `3.1.33`. Текущий rollout: {windowsAssignment ? `${windowsAssignment.channel}/${windowsAssignment.version}` : "не назначен"}.
              </span>
              <Button
                disabled={assignMutation.isPending || stable33133.is_rollout_assigned}
                leadingIcon={<ShieldCheck className="h-4 w-4" />}
                onClick={() => assignMutation.mutate(stable33133)}
                size="sm"
              >
                Сделать 3.1.33 preferred
              </Button>
            </div>
          ) : (
            <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-4 text-sm text-amber-900">
              Windows stable `3.1.33` пока не найден в загруженных builds. Загрузите ZIP через форму ниже.
            </div>
          )}
          {feedback ? <p className="text-sm text-slate-600">{feedback}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Загрузить build</CardTitle>
          <CardDescription>Загрузка идёт в существующий registry `agent_builds`; overwrite не используется.</CardDescription>
        </CardHeader>
        <CardContent>
          <form
            className="grid gap-4 lg:grid-cols-[1fr_120px_140px_160px] xl:grid-cols-[1fr_120px_140px_160px_190px]"
            onSubmit={(event) => {
              event.preventDefault();
              uploadMutation.mutate();
            }}
          >
            <label className="space-y-2 text-sm">
              <span className="font-medium text-slate-700">Файл</span>
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => {
                  setDraft((current) => ({ ...current, file: event.target.files?.[0] ?? null }));
                }}
                type="file"
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium text-slate-700">Target</span>
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, target: event.target.value }))}
                value={draft.target}
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium text-slate-700">Channel</span>
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, channel: event.target.value }))}
                value={draft.channel}
              />
            </label>
            <label className="space-y-2 text-sm">
              <span className="font-medium text-slate-700">Version</span>
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, version: event.target.value }))}
                placeholder="3.1.33"
                value={draft.version}
              />
            </label>
            <div className="flex items-end gap-2">
              <Select
                aria-label="Archive type"
                onChange={(event) =>
                  setDraft((current) => ({ ...current, archiveType: event.target.value as "zip" | "tar.gz" }))
                }
                value={draft.archiveType}
              >
                <option value="zip">zip</option>
                <option value="tar.gz">tar.gz</option>
              </Select>
              <Button
                disabled={uploadMutation.isPending}
                leadingIcon={<Upload className="h-4 w-4" />}
                type="submit"
              >
                Загрузить
              </Button>
            </div>
            <label className="space-y-2 text-sm lg:col-span-4 xl:col-span-5">
              <span className="font-medium text-slate-700">Notes</span>
              <input
                className="field-base w-full px-3 py-2 text-sm"
                onChange={(event) => setDraft((current) => ({ ...current, notes: event.target.value }))}
                placeholder="Например: Remote Assist runtime fixes."
                value={draft.notes}
              />
            </label>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <CardTitle>Реестр builds</CardTitle>
              <CardDescription>Download/delete и назначение target rollout работают с серверным registry.</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <SearchField
                className="w-[280px]"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Поиск по версии, target, sha..."
                value={query}
              />
              <Select onChange={(event) => setTargetFilter(event.target.value)} value={targetFilter}>
                <option value="all">Все target</option>
                {targets.map((target) => (
                  <option key={target} value={target}>
                    {target}
                  </option>
                ))}
              </Select>
              <Select onChange={(event) => setChannelFilter(event.target.value)} value={channelFilter}>
                <option value="all">Все каналы</option>
                {channels.map((channel) => (
                  <option key={channel} value={channel}>
                    {channel}
                  </option>
                ))}
              </Select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {buildsQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем build registry…</p> : null}
          {buildsQuery.isError ? (
            <p className="text-sm text-rose-600">
              {buildsQuery.error instanceof Error ? buildsQuery.error.message : "Не удалось загрузить builds."}
            </p>
          ) : null}
          {!buildsQuery.isLoading && groups.length === 0 ? (
            <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-8 text-center text-sm text-slate-500">
              Builds по текущим фильтрам не найдены.
            </div>
          ) : null}
          {groups.map((group) => (
            <div className="overflow-hidden rounded-[1.2rem] border border-border" key={group.target}>
              <div className="flex items-center justify-between border-b border-border bg-surface-subtle px-5 py-4">
                <div>
                  <p className="text-sm font-semibold text-slate-950">{group.target}</p>
                  <p className="mt-1 text-xs text-slate-500">{group.builds.length} builds</p>
                </div>
                <Badge tone={findAssignment(assignments, group.target) ? "success" : "neutral"} withDot>
                  {assignmentLabel(findAssignment(assignments, group.target))}
                </Badge>
              </div>
              <div className="divide-y divide-border">
                {group.builds.map((build) => (
                  <div
                    className={cn(
                      "grid gap-4 px-5 py-4 xl:grid-cols-[minmax(0,1.1fr)_120px_120px_150px_230px]",
                      build.is_rollout_assigned ? "bg-brand-50/70" : "bg-white"
                    )}
                    key={buildKey(build)}
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-slate-950">{build.version}</p>
                        <Badge tone={build.is_rollout_assigned ? "success" : "neutral"} withDot={build.is_rollout_assigned}>
                          {build.is_rollout_assigned ? "Preferred" : build.channel}
                        </Badge>
                        {build.version === "3.1.33" && build.target === "windows_amd64" ? (
                          <Badge tone="info">Remote Assist fix</Badge>
                        ) : null}
                      </div>
                      <p className="mt-2 truncate text-sm text-slate-500">{build.artifact_filename}</p>
                      <p className="mt-1 text-xs text-slate-400">SHA256 {compactHash(build.sha256)}</p>
                      {build.notes ? <p className="mt-2 text-sm text-slate-600">{build.notes}</p> : null}
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Канал</p>
                      <p className="mt-1 text-sm font-medium text-slate-800">{build.channel}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Архив</p>
                      <p className="mt-1 text-sm font-medium text-slate-800">{build.archive_type}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Размер</p>
                      <p className="mt-1 text-sm font-medium text-slate-800">{formatBytes(build.size)}</p>
                      <p className="mt-1 text-xs text-slate-400">{formatDateTime(build.created_at)}</p>
                    </div>
                    <div className="flex flex-wrap items-start justify-end gap-2">
                      <a href={build.download_path}>
                        <Button leadingIcon={<Download className="h-4 w-4" />} size="sm" variant="outline">
                          Скачать
                        </Button>
                      </a>
                      <Button
                        disabled={assignMutation.isPending || build.is_rollout_assigned}
                        leadingIcon={<CheckCircle2 className="h-4 w-4" />}
                        onClick={() => assignMutation.mutate(build)}
                        size="sm"
                      >
                        Preferred
                      </Button>
                      <Button
                        disabled={deleteMutation.isPending || build.is_rollout_assigned}
                        leadingIcon={<Trash2 className="h-4 w-4" />}
                        onClick={() => {
                          if (window.confirm(`Удалить build ${buildLabel(build)}?`)) {
                            deleteMutation.mutate(build);
                          }
                        }}
                        size="sm"
                        variant="outline"
                      >
                        Удалить
                      </Button>
                      {build.delete_block_reason ? (
                        <p className="basis-full text-right text-xs text-slate-500">Удаление заблокировано: active rollout.</p>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
