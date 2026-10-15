import { newBlock, newKey } from "./scenario-builder-model";
import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";

export type ScenarioStarter = "simple" | "diagnostic" | "empty";
export const starterChoices: { kind: ScenarioStarter; title: string; description: string; route: string }[] = [
  { kind: "simple", title: "Простая заявка", description: "Собрать ответы и передать обращение в поддержку", route: "Пункт каталога → вопрос → сводка → создать обращение" },
  { kind: "diagnostic", title: "Диагностика проблемы", description: "Помочь сотруднику и проверить, удалось ли решить проблему", route: "Инструкция → проверка → подтверждённое решение или обращение" },
  { kind: "empty", title: "Пустая карта", description: "Самостоятельно добавить первый шаг и построить маршрут", route: "Настройки карты и действие «Добавить первый шаг»" },
];

/** Editable schema-v3 drafts, never publication or catalog mutations. */
export function createScenarioStarter(title: string, kind: ScenarioStarter, serviceCode: string, categoryId: string | null): ScenarioDraftDefinition {
  const blocks: ScenarioBlock[] = [];
  if (kind === "simple") {
    const question = newBlock("form_page"), review = newBlock("review"), result = newBlock("submit_ticket");
    question.title = "Что нужно сотруднику?";
    if (question.kind === "form_page") { question.layout = "single"; question.fields[0].label = "Что вам необходимо?"; question.fields[0].required = true; }
    review.title = "Проверка ответов"; result.title = "Создать обращение";
    question.transitions = [{ to: review.id }]; review.transitions = [{ to: result.id }];
    blocks.push(question, review, result);
  } else if (kind === "diagnostic") {
    const instruction = newBlock("instruction"), check = newBlock("resolution_check"), finish = newBlock("finish"), review = newBlock("review"), result = newBlock("submit_ticket");
    instruction.title = "Первый шаг решения"; check.title = "Проблема решена?"; finish.title = "Завершить без обращения";
    review.title = "Передать в поддержку"; result.title = "Создать обращение";
    instruction.transitions = [{ to: check.id }];
    check.transitions = [{ to: finish.id, when: { source: "current_result", op: "eq", value: "yes" } }, { to: review.id, when: { source: "current_result", op: "eq", value: "no" } }, { to: review.id }];
    review.transitions = [{ to: result.id }]; blocks.push(instruction, check, finish, review, result);
  }
  const positions = Object.fromEntries(blocks.map((block, i) => [block.id, kind === "simple" ? [{ x: 0, y: 0 }, { x: 310, y: 0 }, { x: 310, y: 170 }][i] : [{ x: 0, y: 0 }, { x: 310, y: 0 }, { x: 620, y: -90 }, { x: 310, y: 180 }, { x: 620, y: 180 }][i]]));
  return { schema_version: 3, scenario_key: newKey("scenario"), title: title.trim(), description: "", service_code: serviceCode, category_id: categoryId,
    offering_full_code: "", processing: { routes: {}, sla_profiles: {}, defaults: { route: "", sla_profile: "" }, assignment_mode: "last_matching_branch" }, process_binding: { request_template_key: "" }, blocks, entry_block_id: blocks[0]?.id ?? null,
    entry_points: blocks.length ? [{ key: newKey("entry"), title: title.trim(), category_id: categoryId, target_block_id: blocks[0].id, enabled: true, visibility: "public" }] : [],
    editor_layout: { positions: { ...positions, system_start: { x: -340, y: -160 } } } };
}
