import { Button } from "../../components/ui/button";
import type { ScenarioPublicationOutcome } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import type { ScenarioIssueDestination } from "./scenario-issue-navigation";
import { actualSourceLabel } from "./scenario-terminal-sla-model";

function minutes(value?: number) { return value !== undefined && value !== null ? `${value} мин.` : "Не определён"; }
export function ScenarioPublicationOutcomes({ outcomes, definition, onIssue }: { outcomes?: ScenarioPublicationOutcome[]; definition?: ScenarioDraftDefinition; onIssue?: (destination: ScenarioIssueDestination) => void }) {
  return <section aria-label="Проверенные исходы" className="scenario-publication-section">
    <h2>Проверенные исходы</h2>
    <p className="text-sm text-slate-600">Результаты сервера для допустимых ответов и входов из каталога. Одинаковое завершение может иметь разные очередь и сроки.</p>
    {!outcomes?.length ? <p>Проверенные исходы отсутствуют. Исправьте замечания и повторите проверку.</p> : <ol className="scenario-publication-outcomes">{outcomes.map((outcome, index) => {
      const terminal = definition?.blocks?.find(block => block.id === outcome.terminal);
      const entrance = definition?.entry_points?.find(entry => entry.key === outcome.entry_point_key);
      const sla = outcome.sla;
      const slaSource = sla?.source ?? sla?.selection?.source ?? outcome.map_processing?.sla_profile?.source;
      const routeSource = outcome.routing?.source ?? outcome.routing?.selection?.source ?? outcome.map_processing?.route?.source;
      return <li key={index} className="scenario-publication-outcome"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="text-sm text-slate-500">Исход {index + 1} · {outcome.kind === "ticket" ? "Обращение в поддержку" : "Без обращения в поддержку"}</p><h3>{terminal?.title ?? "Завершение сценария"}</h3></div>{onIssue && terminal && <Button variant="ghost" onClick={() => onIssue({ step: 1, blockId: terminal.id, label: terminal.title })}>На карте</Button>}</div>
        <dl className="scenario-publication-facts"><div><dt>Вход из каталога</dt><dd>{entrance?.title ?? (outcome.entry_point_key ? "Дополнительный вход" : "Основной вход")}</dd></div>
          {outcome.kind === "ticket" && <><div><dt>Очередь</dt><dd>{outcome.routing?.queue_title || outcome.routing?.queue_code || "Не определена"}</dd></div><div><dt>Первый ответ</dt><dd>{minutes(sla?.first_response_min)}</dd></div><div><dt>Срок выполнения</dt><dd>{minutes(sla?.resolution_min)}</dd></div><div><dt>Учёт времени</dt><dd>{sla?.time_basis === "business" ? "Рабочее время" : sla?.time_basis === "calendar" ? "Календарное время" : "Не определён"}</dd></div><div><dt>Поддержка: назначение исполнителя</dt><dd>{minutes(outcome.ola?.ack_min)}</dd></div><div><dt>Поддержка: обработка группой</dt><dd>{minutes(outcome.ola?.processing_min)}</dd></div><div><dt>Согласование</dt><dd>{outcome.approval_required === undefined ? "Не определено" : outcome.approval_required ? "Требуется" : "Не требуется"}</dd></div></>}
        </dl>
        {outcome.ola?.enabled === false && <p role="alert" className="text-sm">Учёт внутренних сроков отключён на сервере: таймеры не будут запущены.</p>}
        {slaSource && <p className="text-sm text-slate-600">Источник сроков для сотрудника: {actualSourceLabel(definition, slaSource)}.</p>}
        {routeSource && <p className="text-sm text-slate-600">Источник очереди: {actualSourceLabel(definition, routeSource)}.</p>}
      </li>;
    })}</ol>}
  </section>;
}
