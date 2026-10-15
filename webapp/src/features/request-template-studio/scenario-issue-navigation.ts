import type { ScenarioPublicationPreview } from "./scenario-api";
import type { ScenarioDraftDefinition, ScenarioPolicyKind } from "./scenario-contract";

export type ScenarioIssueDestination = { step: number; label: string; blockId?: string; transitions?: boolean; policy?: ScenarioPolicyKind };
export function scenarioIssueDestination(issue: Pick<ScenarioPublicationPreview["readiness"]["issues"][number], "code" | "path">, definition: ScenarioDraftDefinition): ScenarioIssueDestination {
  const path = issue.path || "";
  if (path === "processing" || path.startsWith("processing.")) return { step: 2, label: path.includes("sla_profiles") || path.includes("sla_profile") ? "Сроки обработки карты" : "Направления и обработка карты" };
  const entrance = definition.entry_points?.find(entry => path === `entry_points.${entry.key}` || path.startsWith(`entry_points.${entry.key}.`));
  if (entrance) return { step: 1, label: entrance.title, blockId: entrance.target_block_id };
  const block = definition.blocks?.find(item => path === `blocks.${item.id}` || path.startsWith(`blocks.${item.id}.`));
  if (block) return { step: 1, label: block.title, blockId: block.id, transitions: path.endsWith(".transitions") };
  const policy: Partial<Record<string, ScenarioPolicyKind>> = { routing_unavailable: "routing", sla_unavailable: "sla", closure_missing: "closure", visibility_missing: "visibility", approval_unavailable: "approval" };
  const kind = policy[issue.code];
  const labels: Partial<Record<ScenarioPolicyKind, string>> = { routing: "Маршрут и очередь", sla: "Сроки обслуживания", closure: "Закрытие обращения", visibility: "Видимость обращения", approval: "Согласование" };
  if (kind) return { step: 2, policy: kind, label: labels[kind]! };
  if (path.startsWith("process_binding")) return { step: 2, label: "Обработка обращения" };
  if (path.startsWith("blocks") || path === "entry_block_id" || path.startsWith("entry_points") || path.startsWith("editor_layout")) return { step: 1, label: "Карта сценария" };
  return { step: 0, label: "Категория и назначение" };
}
