import { Button } from "../../components/ui/button";
import type { ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { scenarioIssueDestination, type ScenarioIssueDestination } from "./scenario-issue-navigation";
import { publicationIssueGuidance } from "./scenario-publication-guidance";

type Issue = ScenarioPublicationPreview["readiness"]["issues"][number];
const groups = ["Каталог и доступность", "Карта и переходы", "Обработка и сроки"];
export function publicationIssueGroup(issue: Issue) {
  const path = issue.path ?? "";
  if (/^(title|description|entry_points|category_id|offering|service_code|publish_offering)/.test(path) || /category|offering|entrance/.test(issue.code)) return 0;
  if (/^(blocks|entry_block_id|editor_layout)/.test(path) || /fallback|unreachable|coverage|cycle|transition/.test(issue.code)) return 1;
  return 2;
}
export function ScenarioPublicationChecks({ preview, definition, onIssue, groupIndex }: { preview: ScenarioPublicationPreview; definition?: ScenarioDraftDefinition; onIssue?: (destination: ScenarioIssueDestination) => void; groupIndex?: number }) {
  return <section className={groupIndex === undefined ? "scenario-publication-section" : "scenario-publication-inline-issues"} aria-label={groupIndex === undefined ? "Результаты проверки" : `Замечания: ${groups[groupIndex]}`}>
    {groupIndex === undefined && <><h2>Проверка перед публикацией</h2>
    <p className={preview.readiness.can_publish ? "text-emerald-800" : "text-amber-900"}>{preview.readiness.can_publish ? "Серверная проверка пройдена. Можно подтвердить публикацию." : "Публикация пока недоступна. Исправьте замечания и повторите проверку."}</p>
    <p>Проверено исходов: {preview.readiness.variants_checked}.</p>
    {preview.readiness.variants_checked === 0 && preview.readiness.issues.length > 0 && <p className="text-sm text-slate-600">Пути пока не проверены. Сначала исправьте указанные настройки, затем повторите проверку.</p>}
    <p className="text-sm text-slate-600">Проверка действующих правил обработки: {preview.health.health_status === "ok" ? "пройдена" : "есть замечания"}.</p>
    </>}
    {groups.map((title, index) => {
      if (groupIndex !== undefined && index !== groupIndex) return null;
      const issues = preview.readiness.issues.filter(issue => publicationIssueGroup(issue) === index);
      return issues.length > 0 && <section key={title} className="scenario-publication-check-group"><h3>{title}</h3><ul>{issues.map((issue, position) => {
        const destination = definition ? scenarioIssueDestination(issue, definition) : null;
        const guidance = publicationIssueGuidance(issue);
        return <li key={`${issue.code}-${position}`}><div className="min-w-0 space-y-1"><p role="alert" className="font-medium">{guidance.title}</p>{/^(sla|routing)_unavailable$/.test(issue.code) && issue.message !== guidance.title && <p className="break-words text-sm">{issue.message}</p>}{guidance.help && <p className="text-sm text-slate-600">{guidance.help}</p>}</div>{destination && onIssue && <Button variant="outline" onClick={() => onIssue(destination)}>Исправить: {destination.label}</Button>}</li>;
      })}</ul></section>;
    })}
  </section>;
}
