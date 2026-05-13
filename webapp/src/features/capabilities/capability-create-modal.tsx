import { useQuery } from "@tanstack/react-query";
import { DatabaseZap, FileCode2, MonitorCog, PlugZap, ScreenShare, UserCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { createAgentRecipe, listAgentRecipePrimitives, publishAgentRecipe, validateAgentRecipe } from "./api";
import type { AgentRecipeCreateResult, AgentRecipePrimitive } from "./types";

type CapabilityCreateModalProps = {
  open: boolean;
  onClose: () => void;
  onCreated?: (result: AgentRecipeCreateResult) => void;
};

type TargetMode = "agent_recipe" | "sdk" | "server_builtin" | "server_connector" | "remote_assist" | "manual";

const TARGET_CARDS = [
  {
    mode: "agent_recipe" as const,
    title: "Проверка на устройстве",
    target: "agent_recipe",
    description: "Без кода: read-only recipe выполняется через protected managed module agent_recipe_runner.",
    status: "MVP",
    icon: MonitorCog,
  },
  {
    mode: "sdk" as const,
    title: "SDK-модуль",
    target: "agent_managed_module",
    description: "ZIP/SDK-модули агента остаются в Modules Workbench.",
    status: "Открыть",
    icon: FileCode2,
  },
  {
    mode: "server_builtin" as const,
    title: "Серверная проверка",
    target: "server_builtin",
    description: "DNS/HTTP и другие server_builtin checks уже доступны в каталоге.",
    status: "Просмотр",
    icon: DatabaseZap,
  },
  {
    mode: "server_connector" as const,
    title: "API-коннектор",
    target: "server_connector",
    description: "Zabbix и внешние API настраиваются через provider config.",
    status: "Providers",
    icon: PlugZap,
  },
  {
    mode: "remote_assist" as const,
    title: "Удаленная помощь",
    target: "remote_assist",
    description: "Remote Assist представлен как capability, создание новых modes не входит в этот релиз.",
    status: "Готово",
    icon: ScreenShare,
  },
  {
    mode: "manual" as const,
    title: "Ручная проверка",
    target: "manual",
    description: "Manual evidence доступен в Diagnostic Center; шаблоны появятся позже.",
    status: "Phase 2",
    icon: UserCheck,
  },
];

export function CapabilityCreateModal({ open, onClose, onCreated }: CapabilityCreateModalProps) {
  const navigate = useNavigate();
  const [mode, setMode] = useState<TargetMode>("agent_recipe");
  const [title, setTitle] = useState("Проверить службу печати");
  const [canonicalId, setCanonicalId] = useState("endpoint.spooler.status");
  const [description, setDescription] = useState("Проверяет состояние службы печати на endpoint.");
  const [platforms, setPlatforms] = useState<Array<"win32" | "linux">>(["win32"]);
  const [primitiveId, setPrimitiveId] = useState("service.status");
  const [paramsText, setParamsText] = useState('{"service_name":"Spooler","expected_state":"running"}');
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const primitivesQuery = useQuery({
    queryKey: ["agent-recipe-primitives"],
    queryFn: listAgentRecipePrimitives,
    enabled: open,
    retry: false,
  });
  const primitives = primitivesQuery.data ?? [];
  const filteredPrimitives = useMemo(
    () => primitives.filter((primitive) => platforms.every((platform) => primitive.platforms?.includes(platform))),
    [platforms, primitives],
  );
  const selectedPrimitive = primitives.find((primitive) => primitive.primitive_id === primitiveId);

  if (!open) {
    return null;
  }

  function togglePlatform(platform: "win32" | "linux") {
    setPlatforms((current) => {
      if (current.includes(platform)) {
        return current.length === 1 ? current : current.filter((item) => item !== platform);
      }
      return [...current, platform];
    });
  }

  async function createValidatePublish() {
    setBusy(true);
    setStatus(null);
    try {
      const params = JSON.parse(paramsText || "{}") as Record<string, unknown>;
      const result = await createAgentRecipe({
        canonical_id: canonicalId,
        title,
        description,
        primitive_id: primitiveId,
        primitive_version: selectedPrimitive?.primitive_version ?? "1.0",
        platforms,
        min_runner_version: "1.0.0",
        domain: "endpoint",
        evidence_kind: primitiveId.includes("service") ? "endpoint.service" : "endpoint.recipe",
        recipe: { params },
      });
      await validateAgentRecipe(result.recipe_version_id);
      await publishAgentRecipe(result.recipe_version_id);
      setStatus("Capability опубликована. Каталог можно обновить.");
      onCreated?.(result);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Не удалось создать recipe capability");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/35 px-4 py-6" role="dialog" aria-modal="true">
      <div className="max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-[1rem] bg-white shadow-2xl">
        <header className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-brand-700">Target-first wizard</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">Создать capability</h2>
            <p className="mt-2 text-sm text-slate-500">
              MVP создает только read-only Agent Recipe capabilities. SDK Modules и connectors остаются в существующих рабочих местах.
            </p>
          </div>
          <Button aria-label="Закрыть" onClick={onClose} size="icon" variant="ghost">
            <X className="h-4 w-4" />
          </Button>
        </header>
        <div className="grid max-h-[76vh] overflow-y-auto lg:grid-cols-[1fr_1.2fr]">
          <div className="grid gap-3 border-r border-border p-5">
            {TARGET_CARDS.map((card) => {
              const Icon = card.icon;
              const active = mode === card.mode;
              return (
                <button
                  className={`rounded-[0.75rem] border px-4 py-3 text-left transition ${
                    active ? "border-brand-400 bg-brand-50" : "border-border bg-white hover:border-brand-200"
                  }`}
                  key={card.mode}
                  onClick={() => {
                    if (card.mode === "sdk") {
                      navigate("/app/admin/modules");
                      onClose();
                      return;
                    }
                    setMode(card.mode);
                  }}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <span className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[0.65rem] bg-white text-brand-700">
                        <Icon className="h-5 w-5" />
                      </span>
                      <span>
                        <span className="block font-semibold text-slate-950">{card.title}</span>
                        <span className="mt-1 block text-xs text-slate-500">{card.target}</span>
                      </span>
                    </span>
                    <Badge tone={card.status === "Phase 2" ? "warning" : "info"}>{card.status}</Badge>
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{card.description}</p>
                </button>
              );
            })}
          </div>
          <div className="space-y-5 p-6">
            {mode !== "agent_recipe" ? (
              <div className="rounded-[0.75rem] border border-dashed border-border p-5">
                <h3 className="text-lg font-semibold text-slate-950">Будет доступно позже</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Этот target уже отображается в Capability Studio, но production authoring flow для него не включен в Agent Recipe Runner release.
                </p>
              </div>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-1 text-sm font-medium text-slate-700">
                    Название
                    <input className="w-full rounded-md border border-border px-3 py-2 text-sm" value={title} onChange={(event) => setTitle(event.target.value)} />
                  </label>
                  <label className="space-y-1 text-sm font-medium text-slate-700">
                    Canonical ID
                    <input className="w-full rounded-md border border-border px-3 py-2 text-sm" value={canonicalId} onChange={(event) => setCanonicalId(event.target.value)} />
                  </label>
                </div>
                <label className="block space-y-1 text-sm font-medium text-slate-700">
                  Описание
                  <textarea className="min-h-20 w-full rounded-md border border-border px-3 py-2 text-sm" value={description} onChange={(event) => setDescription(event.target.value)} />
                </label>
                <div>
                  <p className="text-sm font-medium text-slate-700">Платформы</p>
                  <div className="mt-2 flex gap-2">
                    <Button onClick={() => togglePlatform("win32")} size="sm" variant={platforms.includes("win32") ? "primary" : "outline"}>
                      Windows
                    </Button>
                    <Button onClick={() => togglePlatform("linux")} size="sm" variant={platforms.includes("linux") ? "primary" : "outline"}>
                      Linux
                    </Button>
                    <Badge tone="neutral">macOS не поддерживается</Badge>
                  </div>
                </div>
                <label className="block space-y-1 text-sm font-medium text-slate-700">
                  Примитив
                  <select className="w-full rounded-md border border-border px-3 py-2 text-sm" value={primitiveId} onChange={(event) => setPrimitiveId(event.target.value)}>
                    {(filteredPrimitives.length ? filteredPrimitives : primitives).map((primitive: AgentRecipePrimitive) => (
                      <option key={`${primitive.primitive_id}:${primitive.primitive_version}`} value={primitive.primitive_id}>
                        {primitive.title} · {primitive.primitive_id} · {primitive.platforms?.join(", ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block space-y-1 text-sm font-medium text-slate-700">
                  Recipe params JSON
                  <textarea className="min-h-28 w-full rounded-md border border-border px-3 py-2 font-mono text-xs" value={paramsText} onChange={(event) => setParamsText(event.target.value)} />
                </label>
                <div className="rounded-[0.75rem] border border-border bg-slate-50 p-4 text-sm text-slate-600">
                  <p className="font-semibold text-slate-900">Safety</p>
                  <p className="mt-1">Read-only locked, no shell, no remediation, timeout/resource limits enforced by runner.</p>
                </div>
                {status ? <p className="rounded-[0.75rem] border border-border px-4 py-3 text-sm text-slate-700">{status}</p> : null}
                <div className="flex justify-end gap-2">
                  <Button onClick={onClose} variant="outline">
                    Закрыть
                  </Button>
                  <Button disabled={busy || !title || !canonicalId || !primitiveId || platforms.length === 0} onClick={createValidatePublish}>
                    {busy ? "Публикация..." : "Создать, validate, publish"}
                  </Button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
