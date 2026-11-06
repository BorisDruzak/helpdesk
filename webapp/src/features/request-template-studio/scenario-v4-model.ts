import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";
import { newKey } from "./scenario-builder-model";
export function upgradeScenarioDraft(definition: ScenarioDraftDefinition): ScenarioDraftDefinition {
  return definition.schema_version === 4 ? definition : { ...definition, schema_version: 4, execution_semantics: definition.schema_version ?? 1 };
}
export function setNavigationMode(block: ScenarioBlock, mode: "automatic" | "buttons"): ScenarioBlock {
  if (mode === "buttons" && (block.transitions?.length ?? 0) > 10) throw new Error("Кнопочный режим поддерживает не более 10 связей. Разделите маршрут явно.");
  return { ...block, transition_mode: mode, transitions: block.transitions?.map(edge => {
    if (mode === "buttons") return { ...edge, button: edge.button ?? { key: newKey("action"), label: "Продолжить" } };
    const { button: _button, ...rest } = edge; return rest;
  }) };
}
