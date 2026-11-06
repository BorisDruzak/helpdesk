import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";
export function upgradeScenarioDraft(definition: ScenarioDraftDefinition): ScenarioDraftDefinition {
  return definition.schema_version === 4 ? definition : { ...definition, schema_version: 4, execution_semantics: definition.schema_version ?? 1 };
}
export function uniqueButtonLabel(preferred: string, used: Iterable<string>) {
  const labels = new Set(used), base = preferred.slice(0, 290) || "Продолжить";
  if (!labels.has(base)) return base;
  let number = 2; while (labels.has(`${base} · ${number}`)) number++;
  return `${base} · ${number}`;
}
export function setNavigationMode(block: ScenarioBlock, mode: "automatic" | "buttons", targetTitle?: (id: string) => string): ScenarioBlock {
  if (mode === "buttons" && (block.transitions?.length ?? 0) > 10) throw new Error("Кнопочный режим поддерживает не более 10 связей. Разделите маршрут явно.");
  const labels = (block.transitions ?? []).flatMap(edge => edge.button ? [edge.button.label] : []);
  return { ...block, transition_mode: mode, transitions: block.transitions?.map(edge => {
    if (mode === "buttons") { if (edge.button) return edge; const label = uniqueButtonLabel(targetTitle?.(edge.to) ?? "Продолжить", labels); labels.push(label); return { ...edge, button: { key: newKey("action"), label } }; }
    const { button: _button, ...rest } = edge; return rest;
  }) };
}
