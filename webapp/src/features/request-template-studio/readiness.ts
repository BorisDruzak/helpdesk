import type { PolicyHealthSimulationResult } from "../policy-health/api";
import type { RequestStudioItem } from "./studio-model";
import { hasBlockingIssue } from "./studio-model";

export type ReadinessSummary = {
  status: "ok" | "warning" | "error";
  blockers: string[];
  recommendations: string[];
  ready: string[];
};

export function buildReadinessSummary(
  item: RequestStudioItem | null | undefined,
  simulationResult?: PolicyHealthSimulationResult,
  options?: {
    hasUnsavedChanges?: boolean;
    hasDraft?: boolean;
  },
): ReadinessSummary {
  if (!item) {
    return {
      status: "warning",
      blockers: ["Тип обращения не выбран."],
      recommendations: ["Выберите опубликованный раздел и тип обращения."],
      ready: [],
    };
  }

  const blockers = [
    !item.service.code ? "Не выбран раздел." : null,
    !item.offering ? "Не выбран тип обращения." : null,
    !item.offering?.public_title ? "Не заполнено название типа обращения." : null,
    !item.template ? "Не выбран сценарий обработки." : null,
    !item.formPreview?.fields.length ? "Не найдена форма пользователя." : null,
    ...item.processBlocks.filter((block) => block.status === "error").map((block) => block.explanation),
    ...(item.health?.issues.filter(hasBlockingIssue).map((issue) => issue.message) ?? []),
  ].filter(Boolean) as string[];

  const recommendations = [
    ...item.processBlocks.filter((block) => block.status === "recommended").map((block) => block.explanation),
    ...item.processProfile.recommendedMissing.map((label) => `Проверьте, нужен ли блок: ${label}.`),
    options?.hasUnsavedChanges ? "Есть несохранённые изменения. Сохраните черновик перед проверкой и экспертной публикацией." : null,
    simulationResult ? null : "Запустите тестовый прогон перед публикацией.",
    item.isTechnical ? "Выбран тестовый или выведенный объект. Для рабочей настройки выберите опубликованный тип обращения." : null,
  ].filter(Boolean) as string[];

  const ready = [
    item.service ? "Раздел выбран." : null,
    item.offering ? "Тип обращения выбран." : null,
    item.formPreview?.fields.length ? "Форма содержит поля." : null,
    item.processProfile.readyLabels.length ? `Правила настроены: ${item.processProfile.readyLabels.join(", ")}.` : null,
    options?.hasDraft && !options.hasUnsavedChanges ? "Черновик сохранён." : null,
    item.health && !item.health.issues.some(hasBlockingIssue) ? "Блокирующие ошибки Policy Health не найдены." : null,
    simulationResult ? "Тестовый прогон выполнен." : null,
  ].filter(Boolean) as string[];

  return {
    status: blockers.length ? "error" : recommendations.length ? "warning" : "ok",
    blockers: unique(blockers),
    recommendations: unique(recommendations),
    ready: unique(ready),
  };
}

function unique(items: string[]) {
  return [...new Set(items)].slice(0, 8);
}
