import type { ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";

export type ScenarioIssueDestination = { step: number; label: string; blockId?: string; transitions?: boolean; policy?: ScenarioPolicyKind };
export function scenarioIssueDestination(issue: Pick<ScenarioPublicationPreview["readiness"]["issues"][number], "code" | "path">, definition: ScenarioDraftDefinition): ScenarioIssueDestination {
  const path = issue.path || "";
  const block = definition.blocks?.find(item => path === `blocks.${item.id}` || path.startsWith(`blocks.${item.id}.`));
  if (block) return { step: 1, label: block.title, blockId: block.id, transitions: path.endsWith(".transitions") };
  const policy: Partial<Record<string, ScenarioPolicyKind>> = { routing_unavailable: "routing", sla_unavailable: "sla", closure_missing: "closure", visibility_missing: "visibility", approval_unavailable: "approval" };
  const kind = policy[issue.code];
  const labels: Partial<Record<ScenarioPolicyKind, string>> = { routing: "Маршрут и очередь", sla: "Сроки обслуживания", closure: "Закрытие обращения", visibility: "Видимость обращения", approval: "Согласование" };
  if (kind) return { step: 2, policy: kind, label: labels[kind]! };
  if (path.startsWith("process_binding")) return { step: 2, label: "Обработка обращения" };
  if (path.startsWith("blocks") || path === "entry_block_id") return { step: 1, label: "Пользовательский сценарий" };
  return { step: 0, label: "Категория и назначение" };
}
