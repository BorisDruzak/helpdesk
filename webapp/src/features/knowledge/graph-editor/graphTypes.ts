import type { KnowledgeGraphEdge, KnowledgeGraphNode } from "../api";

export type GraphEditorMode = "select" | "connect" | "add_node" | "pan" | "lasso";

export type NodeDraft = {
  label: string;
  node_type: string;
  visibility: string;
  linked_item_id: string;
  service_code: string;
  offering_code: string;
};

export type EdgeDraft = {
  source_stable_key: string;
  target_stable_key: string;
  relation_type: string;
  visibility: string;
  weight: string;
};

export type SelectedNodeDraft = {
  label: string;
  node_type: string;
  visibility: string;
  status: string;
  linked_item_id: string;
  service_code: string;
  offering_code: string;
};

export type SelectedEdgeDraft = {
  relation_type: string;
  visibility: string;
  status: string;
  weight: string;
  confidence_score: string;
};

export type GraphNodePosition = {
  x: number;
  y: number;
};

export type PositionedGraphNode = KnowledgeGraphNode & GraphNodePosition;

export const fieldClass = "mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-950 outline-none transition-colors focus:border-brand-400 focus:ring-2 focus:ring-brand-100";

export const NODE_TYPE_OPTIONS = [
  { value: "knowledge_item", label: "Статья", shortLabel: "Статья", color: "#2563eb", className: "border-blue-200 bg-blue-50 text-blue-800" },
  { value: "concept", label: "Понятие", shortLabel: "Понятие", color: "#475569", className: "border-slate-200 bg-slate-50 text-slate-800" },
  { value: "service", label: "Сервис", shortLabel: "Сервис", color: "#0f766e", className: "border-teal-200 bg-teal-50 text-teal-800" },
  { value: "offering", label: "Услуга", shortLabel: "Услуга", color: "#d97706", className: "border-amber-200 bg-amber-50 text-amber-800" },
  { value: "known_error", label: "Известная ошибка", shortLabel: "Ошибка", color: "#dc2626", className: "border-rose-200 bg-rose-50 text-rose-800" },
  { value: "workaround", label: "Обходное решение", shortLabel: "Обход", color: "#7c3aed", className: "border-violet-200 bg-violet-50 text-violet-800" },
  { value: "glossary_term", label: "Термин", shortLabel: "Термин", color: "#334155", className: "border-slate-200 bg-slate-100 text-slate-800" },
] as const;

export const RELATION_TYPE_OPTIONS = [
  { value: "mentions", label: "Упоминает", description: "Связанная тема", color: "#2563eb" },
  { value: "belongs_to_service", label: "Относится к сервису", description: "Статья или услуга относится к сервису", color: "#16a34a" },
  { value: "belongs_to_offering", label: "Относится к услуге", description: "Связь с каталоговой услугой", color: "#d97706" },
  { value: "has_known_error", label: "Имеет известную ошибку", description: "Связь с known error", color: "#dc2626" },
  { value: "resolved_by", label: "Решается обходом", description: "Обходное решение устраняет проблему", color: "#7c3aed" },
  { value: "supersedes", label: "Заменяет", description: "Новая статья заменяет старую", color: "#475569" },
  { value: "contradicts", label: "Конфликтует", description: "Правила или статьи противоречат друг другу", color: "#e11d48" },
  { value: "related_to", label: "Связано с", description: "Свободная смысловая связь", color: "#0891b2" },
] as const;

export const VISIBILITY_OPTIONS = [
  { value: "requester", label: "Заявитель" },
  { value: "agent_requester_safe", label: "Безопасно для заявителя" },
  { value: "support_internal", label: "Внутреннее для поддержки" },
  { value: "admin_internal", label: "Административное" },
] as const;

export const STATUS_OPTIONS = [
  { value: "active", label: "Активен" },
  { value: "confirmed", label: "Подтверждён" },
  { value: "proposed", label: "Предложен" },
  { value: "rejected", label: "Отклонён" },
  { value: "archived", label: "В архиве" },
] as const;

export function nodeTypeLabel(value?: string | null) {
  return NODE_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value ?? "Узел";
}

export function nodeTypeShortLabel(value?: string | null) {
  return NODE_TYPE_OPTIONS.find((option) => option.value === value)?.shortLabel ?? value ?? "Узел";
}

export function nodeTypeColor(value?: string | null) {
  return NODE_TYPE_OPTIONS.find((option) => option.value === value)?.color ?? "#64748b";
}

export function nodeTypeClassName(value?: string | null) {
  return NODE_TYPE_OPTIONS.find((option) => option.value === value)?.className ?? "border-slate-200 bg-slate-50 text-slate-800";
}

export function relationTypeLabel(value?: string | null) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === value)?.label ?? value ?? "Связь";
}

export function relationTypeColor(value?: string | null) {
  return RELATION_TYPE_OPTIONS.find((option) => option.value === value)?.color ?? "#64748b";
}

export function visibilityLabel(value?: string | null) {
  return VISIBILITY_OPTIONS.find((option) => option.value === value)?.label ?? value ?? "Не указано";
}

export function statusLabel(value?: string | null) {
  return STATUS_OPTIONS.find((option) => option.value === value)?.label ?? value ?? "Не указано";
}

export function emptyNodeDraft(nodeType = "knowledge_item"): NodeDraft {
  return {
    label: "",
    node_type: nodeType,
    visibility: "support_internal",
    linked_item_id: "",
    service_code: "",
    offering_code: "",
  };
}

export function emptyEdgeDraft(sourceStableKey = ""): EdgeDraft {
  return {
    source_stable_key: sourceStableKey,
    target_stable_key: "",
    relation_type: "mentions",
    visibility: "support_internal",
    weight: "1",
  };
}

export function draftFromNode(node: KnowledgeGraphNode | null): SelectedNodeDraft {
  return {
    label: node?.label ?? "",
    node_type: node?.node_type ?? "knowledge_item",
    visibility: node?.visibility ?? "support_internal",
    status: node?.status ?? "active",
    linked_item_id: node?.linked_item_id ?? "",
    service_code: node?.service_code ?? "",
    offering_code: node?.offering_code ?? "",
  };
}

export function draftFromEdge(edge: KnowledgeGraphEdge | null): SelectedEdgeDraft {
  return {
    relation_type: edge?.relation_type ?? "mentions",
    visibility: edge?.visibility ?? "support_internal",
    status: edge?.status ?? "active",
    weight: String(edge?.weight ?? 1),
    confidence_score: edge?.confidence_score == null ? "" : String(edge.confidence_score),
  };
}

export function parseOptionalNumber(value: string) {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

const translit: Record<string, string> = {
  а: "a",
  б: "b",
  в: "v",
  г: "g",
  д: "d",
  е: "e",
  ё: "e",
  ж: "zh",
  з: "z",
  и: "i",
  й: "y",
  к: "k",
  л: "l",
  м: "m",
  н: "n",
  о: "o",
  п: "p",
  р: "r",
  с: "s",
  т: "t",
  у: "u",
  ф: "f",
  х: "h",
  ц: "ts",
  ч: "ch",
  ш: "sh",
  щ: "sch",
  ъ: "",
  ы: "y",
  ь: "",
  э: "e",
  ю: "yu",
  я: "ya",
};

export function slugifyGraphLabel(label: string) {
  return label
    .trim()
    .toLowerCase()
    .split("")
    .map((char) => translit[char] ?? char)
    .join("")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 72);
}

export function generateStableKey(nodeType: string, label: string) {
  return `${nodeType || "knowledge_item"}:${slugifyGraphLabel(label) || "novyy-uzel"}`;
}

export function nodeDisplayName(node: KnowledgeGraphNode | undefined) {
  return node?.label ?? "Узел не найден";
}
