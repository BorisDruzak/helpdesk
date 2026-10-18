import { Wrench } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminRegistryPayload } from "../api";
import { fetchAdminRegistryScenarioReadiness } from "../api";
import { qualityIssueDescription, qualityIssueTitle, qualitySuggestionDescription, qualitySuggestionTitle, type RegistrySelection } from "./registry-utils";

type QualityIssue = AdminRegistryPayload["data_quality"][number];

type Props = {
  issues: AdminRegistryPayload["data_quality"];
  suggestions: AdminRegistryPayload["suggestions"];
  onFix: (issue: QualityIssue) => void;
  onIgnore: (issue: QualityIssue) => void;
  onSelect: (selection: RegistrySelection) => void;
  onSnooze: (issue: QualityIssue, days: number) => void;
};

export function RegistryQualityTab({ issues, onFix, onIgnore, onSelect, onSnooze, suggestions }: Props) {
  const [readinessVisible, setReadinessVisible] = useState(false);
  const readiness = useQuery({ queryKey: ["admin-registry-scenario-readiness"], queryFn: fetchAdminRegistryScenarioReadiness, enabled: false, retry: false });
  const report = readinessVisible ? readiness.data : undefined;
  const visibleIssues = report?.issues ?? issues;
  function downloadAggregate() {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report.export, null, 2)], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = "registry-scenario-readiness.json"; link.click(); URL.revokeObjectURL(url);
  }
  return (
    <div className="space-y-4">
      <div className="sticky top-0 z-10 rounded-lg border border-border bg-white p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={readiness.isFetching} onClick={() => { setReadinessVisible(true); void readiness.refetch(); }}>Проверить готовность к сценариям</Button>
          {report ? <Button variant="outline" disabled={readiness.isFetching || readiness.isError} onClick={downloadAggregate}>Скачать агрегированный отчёт</Button> : null}
          {readinessVisible ? <Button variant="outline" onClick={() => setReadinessVisible(false)}>Обычное качество данных</Button> : null}
        </div>
        <p className="mt-2 text-xs text-slate-500">Проверка только читает данные. Показывает влияние на конкретную функцию; отсутствие компьютера не блокирует обычное обращение.</p>
        {readiness.isFetching ? <p role="status" className="mt-2 text-sm">Проверяем реестры, политики и опубликованные карты…</p> : null}
        {readiness.isError ? <p role="alert" className="mt-2 text-sm text-rose-700">Проверка не завершена. Повторите попытку; предыдущий результат может быть устаревшим.</p> : null}
      </div>
      {report ? <section aria-label="Результаты готовности к сценариям" className="space-y-3">
        <h2 className="text-lg font-semibold">Готовность к сценариям</h2>
        <div className="flex flex-wrap gap-2">
          <Badge tone="danger">Блокирует конкретную функцию: {report.counts.blocks_function}</Badge>
          <Badge tone="warning">Требует внимания: {report.counts.attention}</Badge>
          <Badge tone="info">Информационно: {report.counts.information}</Badge>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">{report.dimensions.map(dimension => <div key={dimension.key} className="rounded-md border border-border p-2 text-sm"><p className="font-semibold">{dimension.label}</p><p className="text-xs text-slate-500">Блокирует: {dimension.counts.blocks_function} · Внимание: {dimension.counts.attention} · Информация: {dimension.counts.information}</p></div>)}</div>
        {report.organization_trust_impact ? <p className="text-sm text-slate-600">Исторических профилей без подтверждения: {report.organization_trust_impact.counts.legacy_people}. {report.organization_trust_impact.message}</p> : null}
      </section> : null}
      <div className={`grid gap-4 ${report ? "" : "xl:grid-cols-2"}`}>
      <section className="space-y-3">
        <p className="text-sm font-semibold text-slate-950">{report ? "Причины и затронутые функции" : "Проблемы качества данных"}</p>
        {visibleIssues.length ? visibleIssues.map((issue) => (
          <div className="rounded-lg border border-border bg-white px-4 py-3" key={issue.issue_key ?? `${issue.kind}-${issue.object_id}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <Badge tone={issue.severity}>{issue.impact ? ({ blocks_function: "Блокирует конкретную функцию", attention: "Требует внимания", information: "Информационно" })[issue.impact] : qualityIssueTitle(issue)}</Badge>
                <p className="mt-3 font-semibold text-slate-950">{issue.scenario_readiness ? issue.title : qualityIssueTitle(issue)}</p>
                <p className="mt-1 text-sm text-slate-500">{issue.scenario_readiness ? issue.description : qualityIssueDescription(issue)}</p>
                {issue.affected_function ? <p className="mt-1 text-sm">Функция: {issue.affected_function}</p> : null}
                {issue.remediation ? <p className="mt-1 text-sm text-slate-600">Как исправить: {issue.remediation}</p> : null}
                {issue.related_people?.length ? <details className="mt-2 text-sm"><summary className="cursor-pointer">Связанные сотрудники: {issue.related_people.length}</summary><ul className="mt-2 space-y-2">{issue.related_people.map(person => <li key={person.person_id} className="rounded border border-border p-2"><p>{person.label}</p><p className="text-xs text-slate-500">{person.reason}</p><Button size="sm" variant="outline" onClick={() => onSelect({ kind: "person", id: person.person_id })}>Открыть карточку сотрудника</Button></li>)}</ul></details> : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <Button disabled={!issue.device_id && !issue.person_id && !issue.binding_id && !issue.claim_id} onClick={() => {
                  if (issue.binding_id) onSelect({ kind: "binding", id: issue.binding_id });
                  else if (issue.claim_id) onSelect({ kind: "claim", id: issue.claim_id });
                  else if (issue.person_id) onSelect({ kind: "person", id: issue.person_id });
                  else if (issue.device_id) onSelect({ kind: "device", id: issue.device_id });
                }} size="sm" title="Открыть связанный объект реестра" variant="outline">Открыть</Button>
                {issue.fix_href ? <a className="text-sm font-semibold text-brand-700 underline" href={issue.fix_href}>Открыть настройку</a> : !issue.scenario_readiness ? <Button leadingIcon={<Wrench className="h-4 w-4" />} onClick={() => onFix(issue)} size="sm" title="Перейти к безопасному исправлению проблемы">Исправить</Button> : null}
                <Button onClick={() => onIgnore(issue)} size="sm" title="Исключить проблему из активного списка с аудируемой причиной" variant="outline">Игнорировать</Button>
                <Button onClick={() => onSnooze(issue, 7)} size="sm" title="Отложить проблему на 7 дней с указанием причины" variant="outline">Отложить на 7 дней</Button>
              </div>
            </div>
          </div>
        )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Активных критичных проблем нет.</p>}
      </section>
      {!report ? <section className="space-y-3">
        <p className="text-sm font-semibold text-slate-950">Рекомендации</p>
        {suggestions.length ? suggestions.map((suggestion) => (
          <div className="rounded-lg border border-border bg-white px-4 py-3" key={`${suggestion.kind}-${suggestion.object_id}`}>
            <Badge tone="info">{Math.round(suggestion.confidence * 100)}%</Badge>
            <p className="mt-3 font-semibold text-slate-950">{qualitySuggestionTitle(suggestion)}</p>
            <p className="mt-1 text-sm text-slate-500">{qualitySuggestionDescription(suggestion)}</p>
          </div>
        )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Новых рекомендаций нет.</p>}
      </section> : null}
      </div>
    </div>
  );
}
