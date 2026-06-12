import type { KnowledgeApplicabilityRule, KnowledgeMetadataBundle, KnowledgePropertyDefinition, KnowledgeTaxonomyTerm } from "./api";

export const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
export const textareaClass = `${fieldClass} min-h-24`;

export const termTypeOptions = [
  { label: "Категория", value: "category" },
  { label: "Продукт", value: "product" },
  { label: "Тема", value: "topic" },
  { label: "Аудитория", value: "audience" },
  { label: "Тег", value: "tag" },
];

export const visibilityOptions = [
  { label: "Портал заявителя", value: "requester" },
  { label: "Агент и заявитель", value: "agent_requester_safe" },
  { label: "Поддержка", value: "support_internal" },
  { label: "Администраторы", value: "admin_internal" },
  { label: "Безопасность", value: "security_restricted" },
];

export const statusOptions = [
  { label: "Активно", value: "active" },
  { label: "Черновик", value: "draft" },
  { label: "Архив", value: "archived" },
];

export const valueTypeOptions = [
  { label: "Текст", value: "text" },
  { label: "Число", value: "number" },
  { label: "Да/нет", value: "boolean" },
  { label: "Дата", value: "date" },
  { label: "Выбор", value: "select" },
  { label: "Множественный выбор", value: "multi_select" },
  { label: "URL", value: "url" },
];

export const scopeTypeOptions = [
  { label: "Сервис", value: "service" },
  { label: "Услуга", value: "offering" },
  { label: "Шаблон заявки", value: "request_template" },
  { label: "Роль", value: "role" },
  { label: "ОС устройства", value: "device_os" },
  { label: "Семейство устройства", value: "device_family" },
  { label: "Аудитория", value: "audience" },
  { label: "Термин таксономии", value: "taxonomy_term" },
  { label: "Своя область", value: "custom" },
];

export const includeModeOptions = [
  { label: "Включить", value: "include" },
  { label: "Исключить", value: "exclude" },
];

export function splitLines(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function termsForSpace(metadata: KnowledgeMetadataBundle | undefined, spaceId: string) {
  return (metadata?.taxonomy_terms ?? [])
    .filter((term) => term.space_id === spaceId)
    .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.title.localeCompare(b.title, "ru"));
}

export function propertiesForItem(metadata: KnowledgeMetadataBundle | undefined, spaceId: string, itemType: string) {
  return (metadata?.property_definitions ?? []).filter((definition) => {
    if (definition.space_id !== spaceId || definition.status === "archived") {
      return false;
    }
    const itemTypes = definition.applies_to_item_types ?? [];
    return !itemTypes.length || itemTypes.includes(itemType);
  });
}

export function linkedItemCount(metadata: KnowledgeMetadataBundle | undefined, termId: string) {
  return (metadata?.item_metadata ?? []).filter((item) => item.taxonomy_terms?.some((term) => term.term_id === termId)).length;
}

export function taxonomyLabel(term: KnowledgeTaxonomyTerm | undefined) {
  return term ? `${term.title} (${term.code})` : "Без родителя";
}

export function propertyValueToInput(definition: KnowledgePropertyDefinition, value: unknown) {
  if (definition.value_type === "multi_select") {
    return Array.isArray(value) ? value.join("\n") : "";
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  return value == null ? "" : String(value);
}

export function propertyInputToValue(definition: KnowledgePropertyDefinition, value: string): unknown {
  if (definition.value_type === "multi_select") {
    return splitLines(value);
  }
  if (definition.value_type === "number") {
    return Number(value);
  }
  if (definition.value_type === "boolean") {
    return value === "true";
  }
  return value;
}

export function activeQualityScore(terms: string[], properties: Record<string, string>, rules: KnowledgeApplicabilityRule[], definitions: KnowledgePropertyDefinition[]) {
  const requiredMissing = definitions.filter((definition) => definition.required && !String(properties[definition.code] ?? "").trim());
  const dimensions = [terms.length > 0, requiredMissing.length === 0, rules.length > 0];
  return Math.round((dimensions.filter(Boolean).length / dimensions.length) * 100);
}

export function hasMojibake(value: string) {
  return /\uFFFD|\u0420\u045A|\u0420\u045E|\u0420\u040F|\u0421\u045A|\u0421\u201A|\u0421\u2039|\u0421\u0453|\u0421\u2020|\u0421\u2021|\u0421\u02DC/.test(value);
}
