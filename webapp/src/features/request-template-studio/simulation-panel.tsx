import { AlertTriangle, Play } from "lucide-react";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import type { PolicyHealthSimulationResult, PolicySimulationPayload } from "../policy-health/api";
import type { GuidedSimulationDraft } from "./options";
import type { RequestStudioItem } from "./studio-model";
import { statusTone, tech } from "./studio-model";

export function SimulationPanel({
  item,
  draft,
  payload,
  pending,
  result,
  error,
  onDraftChange,
  onRun,
}: {
  item: RequestStudioItem;
  draft: GuidedSimulationDraft;
  payload: PolicySimulationPayload;
  pending: boolean;
  result: PolicyHealthSimulationResult | undefined;
  error: unknown;
  onDraftChange: (key: keyof GuidedSimulationDraft, value: string) => void;
  onRun: () => void;
}) {
  return (
    <section className="surface-panel p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-950">Проверка и симуляция</h2>
          <p className="mt-1 text-sm text-slate-600">Тестовый прогон не требует JSON в базовом режиме.</p>
        </div>
        <Button disabled={!item.template || pending} leadingIcon={<Play className="h-4 w-4" />} onClick={onRun} type="button">
          Запустить проверку
        </Button>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <input className="field-base px-3 py-2" placeholder="Инициатор" value={draft.requester} onChange={(event) => onDraftChange("requester", event.currentTarget.value)} />
        <input className="field-base px-3 py-2" placeholder="Устройство" value={draft.device} onChange={(event) => onDraftChange("device", event.currentTarget.value)} />
        <input className="field-base px-3 py-2" placeholder="Локация" value={draft.location} onChange={(event) => onDraftChange("location", event.currentTarget.value)} />
        <select className="field-base px-3 py-2" value={draft.expectedPriority} onChange={(event) => onDraftChange("expectedPriority", event.currentTarget.value)}>
          <option value="">Ожидаемый приоритет</option>
          <option value="P0">P0</option>
          <option value="P1">P1</option>
          <option value="P2">P2</option>
          <option value="P3">P3</option>
        </select>
        <textarea
          className="field-base min-h-24 px-3 py-2 md:col-span-2"
          placeholder="Краткое содержание/ответы формы"
          value={draft.answerSummary}
          onChange={(event) => onDraftChange("answerSummary", event.currentTarget.value)}
        />
      </div>

      <SimulationResult result={result} error={error} />

      <details className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
        <summary className="cursor-pointer text-sm font-semibold text-slate-700">Экспертный JSON запроса</summary>
        <pre data-testid="studio-simulation-payload" className="mt-3 max-h-56 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-50">
          {JSON.stringify(payload, null, 2)}
        </pre>
      </details>
    </section>
  );
}

function SimulationResult({ result, error }: { result: PolicyHealthSimulationResult | undefined; error: unknown }) {
  if (error) {
    return (
      <div className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
        {error instanceof Error ? error.message : "Симуляция завершилась ошибкой."}
      </div>
    );
  }
  if (!result) {
    return null;
  }
  const rows = [
    ["Заявка попадёт в очередь", getString(result.routing, ["target_queue_name", "target_queue", "queue"])],
    ["Приоритет", getString(result.priority, ["priority", "priority_class", "result"])],
    ["Ответить до", getString(result.sla, ["first_response_due_at", "response_due_at", "sla_target"])],
    ["Решить до", getString(result.sla, ["resolution_due_at", "resolve_due_at", "sla_target"])],
    ["Согласование", getString(result.approval, ["required", "decision", "mode"])],
    ["Пользователь увидит статус", getString(result.visibility, ["public_status", "status", "mode"])],
    ["Публикация", result.warnings?.length ? "разрешена с предупреждениями" : "разрешена по симуляции"],
  ];
  return (
    <div className="mt-4 rounded-md border border-slate-200 bg-white p-4">
      <h3 className="font-semibold text-slate-950">Результат тестового прогона</h3>
      {result.warnings?.length ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <div className="flex items-center gap-2 font-semibold">
            <AlertTriangle className="h-4 w-4" />
            Предупреждения
          </div>
          <ul className="mt-2 list-disc pl-5">
            {result.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      ) : null}
      <dl className="mt-3 grid gap-2 md:grid-cols-2">
        {rows.map(([label, value]) => (
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm" key={label}>
            <dt className="text-slate-500">{label}</dt>
            <dd className="mt-1 font-semibold text-slate-950">{tech(value)}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge tone={statusTone(getString(result.routing, ["status"]))}>маршрут</Badge>
        <Badge tone={statusTone(getString(result.sla, ["status"]))}>SLA</Badge>
        <Badge tone={statusTone(getString(result.approval, ["status"]))}>согласование</Badge>
      </div>
    </div>
  );
}

function getString(record: Record<string, unknown> | undefined, keys: string[]) {
  if (!record) {
    return null;
  }
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
  }
  return null;
}
