import type { ReactNode } from "react";

import type { KnowledgeItem, KnowledgeItemVersion, KnowledgeSpace } from "../api";

export const fieldClass = "mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900";
export const textareaClass = `${fieldClass} min-h-24 resize-y`;

export const itemTypeOptions = [
  { label: "Инструкция / статья", value: "article" },
  { label: "FAQ", value: "faq" },
  { label: "Известная ошибка", value: "known_error" },
  { label: "Обходное решение", value: "workaround" },
  { label: "Термин", value: "glossary_term" },
];

export const visibilityOptions = [
  { label: "Портал заявителя", value: "requester" },
  { label: "Безопасно для агента и заявителя", value: "agent_requester_safe" },
  { label: "Внутреннее для поддержки", value: "support_internal" },
  { label: "Только администраторы", value: "admin_internal" },
];

export const aiRagPolicyOptions = [
  { label: "По умолчанию раздела", value: "inherit" },
  { label: "Использовать в AI/RAG", value: "allowed" },
  { label: "Не использовать в AI/RAG", value: "disabled" },
  { label: "Только поддержка и администраторы", value: "staff_only" },
  { label: "Только requester-safe ответы", value: "requester_safe_only" },
];

export const statusFilterOptions = [
  { label: "Все", value: "all" },
  { label: "Черновики", value: "draft" },
  { label: "Опубликованные", value: "published" },
  { label: "Архив", value: "archived" },
];

export const editorSteps = [
  { label: "Текст", value: "text" },
  { label: "Настройки", value: "metadata" },
  { label: "Проверка", value: "validation" },
];

export const editorQuickViews = [
  { label: "Редактор", value: "text" },
  { label: "Preview", value: "preview" },
  { label: "Diff", value: "validation" },
  { label: "История", value: "history" },
];

const statusLabels: Record<string, string> = {
  archived: "Архив",
  draft: "Черновик",
  in_review: "На ревью",
  published: "Опубликована",
  retired: "Выведена",
};

export type EditorDraft = {
  ai_rag_policy: string;
  body: string;
  body_format: string;
  change_summary: string;
  item_type: string;
  owner_actor_id: string;
  reviewer_actor_id: string;
  slug: string;
  space_code: string;
  summary: string;
  tags: string;
  title: string;
  visibility: string;
};

export type NewItemDraft = {
  item_type: string;
  owner_actor_id: string;
  reviewer_actor_id: string;
  slug: string;
  space_code: string;
  summary: string;
  tags: string;
  title: string;
  visibility: string;
};

export type EditorSelectionSnapshot = {
  from: number;
  text: string;
  to: number;
};

export type ValidationCheck = {
  key: string;
  label: string;
  ok: boolean;
  detail?: string;
};

export function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

export function spaceCodeFor(item: KnowledgeItem | null, spaces: Array<Pick<KnowledgeSpace, "code" | "space_id">>) {
  if (!item) {
    return spaces[0]?.code ?? "";
  }
  return spaces.find((space) => space.space_id === item.space_id)?.code ?? spaces[0]?.code ?? "";
}

export function draftFrom(
  item: KnowledgeItem | null,
  version: KnowledgeItemVersion | null,
  spaces: Array<Pick<KnowledgeSpace, "code" | "space_id">>,
): EditorDraft {
  const metadata = item?.metadata ?? {};
  const aiRagPolicy = typeof metadata.ai_rag_policy === "string" ? metadata.ai_rag_policy : "inherit";
  return {
    ai_rag_policy: aiRagPolicy,
    body: version?.body ?? "",
    body_format: version?.body_format ?? "markdown",
    change_summary: "",
    item_type: item?.item_type ?? "article",
    owner_actor_id: item?.owner_actor_id ?? "",
    reviewer_actor_id: item?.reviewer_actor_id ?? "",
    slug: item?.slug ?? "",
    space_code: spaceCodeFor(item, spaces),
    summary: version?.summary ?? item?.summary ?? "",
    tags: (item?.tags ?? []).join(", "),
    title: version?.title ?? item?.title ?? "",
    visibility: item?.visibility ?? "requester",
  };
}

export function normalizeList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function statusLabel(value: string | null | undefined) {
  if (!value) {
    return "Без статуса";
  }
  return statusLabels[value] ?? value;
}

export function visibilityLabel(value: string | null | undefined) {
  return visibilityOptions.find((option) => option.value === value)?.label ?? value ?? "Без видимости";
}

export function itemTypeLabel(value: string | null | undefined) {
  return itemTypeOptions.find((option) => option.value === value)?.label ?? value ?? "Материал";
}

export function markdownPreview(markdown: string): ReactNode {
  const blocks = markdown
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  if (!blocks.length) {
    return <p className="text-sm text-slate-500">Предпросмотр появится после заполнения текста статьи.</p>;
  }

  return blocks.map((block, index) => {
    if (block.startsWith("# ")) {
      return (
        <h2 key={index} className="text-xl font-semibold text-slate-950">
          {block.slice(2).trim()}
        </h2>
      );
    }
    if (block.startsWith("## ")) {
      return (
        <h3 key={index} className="text-base font-semibold text-slate-900">
          {block.slice(3).trim()}
        </h3>
      );
    }
    if (block.startsWith("- ")) {
      return (
        <ul key={index} className="list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {block.split("\n").map((line) => (
            <li key={line}>{line.replace(/^- /, "")}</li>
          ))}
        </ul>
      );
    }
    return (
      <p key={index} className="text-sm leading-7 text-slate-700">
        {block}
      </p>
    );
  });
}

export function diffSummary(originalBody: string, draftBody: string) {
  const originalLines = originalBody.split("\n").filter((line) => line.trim());
  const draftLines = draftBody.split("\n").filter((line) => line.trim());
  const added = draftLines.filter((line) => !originalLines.includes(line));
  const removed = originalLines.filter((line) => !draftLines.includes(line));
  return { added, removed };
}

export function validationChecksFor(draft: EditorDraft, activeSegmentsCount: number): ValidationCheck[] {
  void activeSegmentsCount;
  return [
    {
      key: "body",
      label: "Текст статьи заполнен",
      ok: Boolean(draft.body.trim()),
    },
    {
      key: "summary",
      label: "Есть краткое описание",
      ok: Boolean(draft.summary.trim()),
    },
    {
      key: "visibility",
      label: "Безопасная видимость выбрана",
      ok: Boolean(draft.visibility),
      detail: visibilityLabel(draft.visibility),
    },
    {
      key: "section",
      label: "Раздел базы знаний выбран",
      ok: Boolean(draft.space_code),
    },
  ];
}
