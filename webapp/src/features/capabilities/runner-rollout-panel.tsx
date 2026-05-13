import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, RefreshCw, RotateCcw, Send, Waves } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { createRunnerRolloutPlan, getRunnerRollout, runRunnerRolloutAction } from "./api";
import { readinessTone } from "./labels";
import type { BadgeProps } from "../../components/ui/badge";
import type { RunnerRolloutPlan } from "./types";

const QUERY_KEY = ["admin-runner-rollout"];

function parseDeviceIds(value: string): string[] | undefined {
  const ids = value
    .split(/[,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  return ids.length > 0 ? ids : undefined;
}

function numberValue(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function statusTone(status: string): NonNullable<BadgeProps["tone"]> {
  if (["completed", "succeeded", "rolled_back"].includes(status)) {
    return "success";
  }
  if (["failed", "canceled"].includes(status)) {
    return "danger";
  }
  if (["paused", "rolling_back", "rollback_desired"].includes(status)) {
    return "warning";
  }
  if (["active", "running", "desired_set", "installing"].includes(status)) {
    return "info";
  }
  return readinessTone(status);
}

function PlanSummary({ plan }: { plan: RunnerRolloutPlan }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <div>
          <p className="text-xs text-slate-400">Target</p>
          <p className="mt-1 font-semibold text-slate-950">{plan.target_version}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Rollback</p>
          <p className="mt-1 font-semibold text-slate-950">{plan.rollback_version ?? "not set"}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Targets</p>
          <p className="mt-1 font-semibold text-slate-950">{plan.target_count}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Status</p>
          <Badge tone={statusTone(plan.status)}>{plan.status}</Badge>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {Object.entries(plan.summary).map(([status, count]) => (
          <Badge key={status} tone={statusTone(status)}>
            {status}: {count}
          </Badge>
        ))}
      </div>
      <div className="overflow-hidden rounded-[0.9rem] border border-border">
        <table className="min-w-full divide-y divide-border text-sm">
          <thead className="bg-surface-subtle text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3 text-left font-semibold">Wave</th>
              <th className="px-4 py-3 text-left font-semibold">Status</th>
              <th className="px-4 py-3 text-left font-semibold">Targets</th>
              <th className="px-4 py-3 text-left font-semibold">Devices</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-white">
            {plan.waves.length === 0 ? (
              <tr>
                <td className="px-4 py-5 text-slate-500" colSpan={4}>
                  Canary wave is not started yet.
                </td>
              </tr>
            ) : (
              plan.waves.map((wave) => (
                <tr key={wave.wave_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">#{wave.wave_index}</td>
                  <td className="px-4 py-3">
                    <Badge tone={statusTone(wave.status)}>{wave.status}</Badge>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{wave.target_count}</td>
                  <td className="px-4 py-3 text-slate-600">
                    <div className="flex flex-wrap gap-1">
                      {wave.targets.map((target) => (
                        <Badge key={target.target_id} tone={statusTone(target.status)}>
                          {target.device_id.slice(0, 8)} {target.status}
                        </Badge>
                      ))}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RunnerRolloutPanel() {
  const queryClient = useQueryClient();
  const [targetVersion, setTargetVersion] = useState("");
  const [rollbackVersion, setRollbackVersion] = useState("");
  const [targetDevices, setTargetDevices] = useState("");
  const [canarySize, setCanarySize] = useState("1");
  const [waveSize, setWaveSize] = useState("10");
  const [maxConcurrency, setMaxConcurrency] = useState("10");
  const [rollbackReason, setRollbackReason] = useState("");

  const rolloutQuery = useQuery({ queryKey: QUERY_KEY, queryFn: getRunnerRollout, retry: false });
  const latestPlan = rolloutQuery.data?.plans[0] ?? rolloutQuery.data?.summary.latest_plan ?? null;
  const versionOptions = useMemo(() => rolloutQuery.data?.summary.versions.map((item) => item.version) ?? [], [rolloutQuery.data]);

  const createMutation = useMutation({
    mutationFn: createRunnerRolloutPlan,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
  const actionMutation = useMutation({
    mutationFn: ({ planId, action, payload }: { planId: string; action: Parameters<typeof runRunnerRolloutAction>[1]; payload?: Record<string, unknown> }) =>
      runRunnerRolloutAction(planId, action, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  const busy = createMutation.isPending || actionMutation.isPending;
  const canCreate = targetVersion.trim().length > 0 && !busy;

  function createPlan() {
    createMutation.mutate({
      target_version: targetVersion.trim(),
      rollback_version: rollbackVersion.trim() || undefined,
      target_device_ids: parseDeviceIds(targetDevices),
      canary_size: numberValue(canarySize, 1),
      wave_size: numberValue(waveSize, 10),
      max_concurrency: numberValue(maxConcurrency, 10),
    });
  }

  function action(actionName: Parameters<typeof runRunnerRolloutAction>[1], payload: Record<string, unknown> = {}) {
    if (!latestPlan) {
      return;
    }
    actionMutation.mutate({ planId: latestPlan.plan_id, action: actionName, payload });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Waves className="h-5 w-5 text-brand-700" />
              Agent Recipe Runner rollout
            </CardTitle>
            <CardDescription>
              Canary, wave rollout and rollback for the protected managed module. Delivery uses desired modules and reconcile.
            </CardDescription>
          </div>
          <Button
            leadingIcon={<RefreshCw className="h-4 w-4" />}
            onClick={() => {
              void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
              if (latestPlan) {
                action("refresh");
              }
            }}
            size="sm"
            variant="outline"
          >
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {rolloutQuery.isError ? (
          <p className="rounded-[0.9rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {rolloutQuery.error instanceof Error ? rolloutQuery.error.message : "Unable to load runner rollout."}
          </p>
        ) : null}
        <div className="grid gap-3 md:grid-cols-4">
          <div>
            <p className="text-xs text-slate-400">Active installs</p>
            <p className="mt-1 text-xl font-semibold text-slate-950">{rolloutQuery.data?.summary.installed_active_devices ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Rollout targets</p>
            <p className="mt-1 text-xl font-semibold text-slate-950">{rolloutQuery.data?.summary.rollout_targets ?? 0}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Known versions</p>
            <p className="mt-1 text-xl font-semibold text-slate-950">{versionOptions.length}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">Latest plan</p>
            <p className="mt-1 text-xl font-semibold text-slate-950">{latestPlan?.status ?? "none"}</p>
          </div>
        </div>

        <div className="grid gap-3 rounded-[0.9rem] border border-border bg-surface-subtle p-4 lg:grid-cols-6">
          <Input list="runner-rollout-versions" onChange={(event) => setTargetVersion(event.target.value)} placeholder="Target version" value={targetVersion} />
          <Input list="runner-rollout-versions" onChange={(event) => setRollbackVersion(event.target.value)} placeholder="Rollback version" value={rollbackVersion} />
          <Input onChange={(event) => setCanarySize(event.target.value)} placeholder="Canary size" value={canarySize} />
          <Input onChange={(event) => setWaveSize(event.target.value)} placeholder="Wave size" value={waveSize} />
          <Input onChange={(event) => setMaxConcurrency(event.target.value)} placeholder="Max concurrency" value={maxConcurrency} />
          <Button disabled={!canCreate} onClick={createPlan} size="sm">
            Create plan
          </Button>
          <Input className="lg:col-span-6" onChange={(event) => setTargetDevices(event.target.value)} placeholder="Optional device ids, separated by comma or space. Empty means installed runner devices." value={targetDevices} />
          <datalist id="runner-rollout-versions">
            {versionOptions.map((version) => (
              <option key={version} value={version} />
            ))}
          </datalist>
        </div>

        {createMutation.isError || actionMutation.isError ? (
          <p className="rounded-[0.9rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {(createMutation.error ?? actionMutation.error) instanceof Error
              ? (createMutation.error ?? actionMutation.error)?.message
              : "Runner rollout action failed."}
          </p>
        ) : null}

        {latestPlan ? (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button disabled={busy || !["draft", "paused"].includes(latestPlan.status)} leadingIcon={<Play className="h-4 w-4" />} onClick={() => action("start-canary")} size="sm">
                Start canary
              </Button>
              <Button disabled={busy || latestPlan.status !== "active"} leadingIcon={<Send className="h-4 w-4" />} onClick={() => action("promote-next-wave")} size="sm" variant="outline">
                Promote wave
              </Button>
              <Button disabled={busy || latestPlan.status !== "active"} leadingIcon={<Pause className="h-4 w-4" />} onClick={() => action("pause")} size="sm" variant="outline">
                Pause
              </Button>
              <Button disabled={busy || latestPlan.status !== "paused"} leadingIcon={<Play className="h-4 w-4" />} onClick={() => action("resume")} size="sm" variant="outline">
                Resume
              </Button>
              <Input className="h-9 max-w-xs" onChange={(event) => setRollbackReason(event.target.value)} placeholder="Rollback reason" value={rollbackReason} />
              <Button disabled={busy || !["active", "paused", "completed", "failed"].includes(latestPlan.status)} leadingIcon={<RotateCcw className="h-4 w-4" />} onClick={() => action("rollback", { reason: rollbackReason })} size="sm" variant="outline">
                Rollback
              </Button>
            </div>
            <PlanSummary plan={latestPlan} />
          </div>
        ) : (
          <p className="rounded-[0.9rem] border border-dashed border-border px-4 py-5 text-sm text-slate-500">
            No runner rollout plan yet. Create a plan for a preferred tested runner version, then start canary.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
