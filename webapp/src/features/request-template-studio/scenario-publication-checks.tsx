import { Button } from "../../components/ui/button";
import type { ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
import { scenarioIssueDestination, type ScenarioIssueDestination } from "./scenario-issue-navigation";

type Issue = ScenarioPublicationPreview["readiness"]["issues"][number];
const groups = ["Каталог и доступность", "Карта и переходы", "Обработка и сроки"];
function group(issue: Issue) {
  const path = issue.path ?? "";
  if (/^(entry_points|category_id|offering|service_code|publish_offering)/.test(path) || /category|offering|visibility|entrance/.test(issue.code)) return 0;
  if (/^(blocks|entry_block_id|editor_layout)/.test(path) || /fallback|unreachable|coverage|cycle|transition/.test(issue.code)) return 1;
  return 2;
}
export function ScenarioPublicationChecks({ preview, definition, onIssue }: { preview: ScenarioPublicationPreview; definition?: ScenarioDraftDefinition; onIssue?: (destination: ScenarioIssueDestination) => void }) {
  return <section className="scenario-publication-section" aria-label="Результаты проверки">
    <h2>Проверка перед публикацией</h2>
    <p className={preview.readiness.can_publish ? "text-emerald-800" : "text-amber-900"}>{preview.readiness.can_publish ? "Серверная проверка пройдена. Можно подтвердить публикацию." : "Публикация пока недоступна. Исправьте замечания и повторите проверку."}</p>
    <p>Проверено исходов: {preview.readiness.variants_checked}.</p>
    <p className="text-sm text-slate-600">Проверка действующих правил обработки: {preview.health.health_status === "ok" ? "пройдена" : "есть замечания"}.</p>
    {groups.map((title, index) => {
      const issues = preview.readiness.issues.filter(issue => group(issue) === index);
      return issues.length > 0 && <section key={title} className="scenario-publication-check-group"><h3>{title}</h3><ul>{issues.map((issue, position) => {
        const destination = definition ? scenarioIssueDestination(issue, definition) : null;
        return <li key={`${issue.code}-${position}`}><p role="alert">{issue.message}</p>{destination && onIssue && <Button variant="outline" onClick={() => onIssue(destination)}>Исправить: {destination.label}</Button>}</li>;
      })}</ul></section>;
    })}
  </section>;
}
