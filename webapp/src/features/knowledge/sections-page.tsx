import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, FolderKanban, Plus, Save, Trash2 } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { PageHeading } from "../../components/ui/page-heading";
import {
  fetchKnowledgeAudienceRules,
  fetchKnowledgeSpaces,
  previewKnowledgeAudienceRules,
  replaceKnowledgeAudienceRules,
  saveKnowledgeSpace,
  type KnowledgeAudiencePreview,
  type KnowledgeAudienceRuleInput,
  type KnowledgeAudienceRuleTargetType,
  type KnowledgeSpace,
} from "./api";
import {
  decisionLabel,
  estimateAudience,
  fetchVisibilityLookups,
  internalVisibilityWarning,
  pluralPeople,
  ruleLabel,
  ruleToDraft,
  targetOptionsFor,
  targetTypeOptions,
  visibilityLabels,
} from "./article-visibility-model";

type SectionDraft = {
  allow_ingestion: boolean;
  allow_publication: boolean;
  allow_rag: boolean;
  code: string;
  description: string;
  lifecycle_status: string;
  title: string;
  visibility: string;
};

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900";
const checkboxClass = "mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500";

const statusOptions = [
  { label: "Черновик", value: "draft" },
  { label: "Активен", value: "active" },
  { label: "В архиве", value: "archived" },
];

const visibilityOptions = [
  "public",
  "requester",
  "agent_requester_safe",
  "support_internal",
  "admin_internal",
  "security_restricted",
  "auditor_read",
];

const domainTabs = [
  { active: true, href: "/app/admin/knowledge/sections", label: "Разделы" },
  { active: false, href: "/app/admin/knowledge/studio", label: "Содержание" },
  { active: false, href: "/app/admin/knowledge/import", label: "Импорт" },
  { active: false, href: "/app/admin/knowledge/graph", label: "Граф" },
  { active: false, href: "/app/admin/knowledge/search-settings", label: "Поиск" },
  { active: false, href: "/app/admin/knowledge/ai", label: "AI" },
  { active: false, href: "/app/admin/knowledge/indexing", label: "Индексация" },
];

function emptyDraft(): SectionDraft {
  return {
    allow_ingestion: true,
    allow_publication: true,
    allow_rag: true,
    code: "",
    description: "",
    lifecycle_status: "draft",
    title: "",
    visibility: "requester",
  };
}

function draftFromSpace(space: KnowledgeSpace | null | undefined): SectionDraft {
  if (!space) {
    return emptyDraft();
  }
  return {
    allow_ingestion: space.allow_ingestion ?? true,
    allow_publication: space.allow_publication ?? true,
    allow_rag: space.allow_rag ?? true,
    code: space.code ?? "",
    description: space.description ?? "",
    lifecycle_status: space.lifecycle_status ?? "draft",
    title: space.title ?? "",
    visibility: space.visibility ?? "requester",
  };
}

function statusLabel(status: string) {
  return statusOptions.find((option) => option.value === status)?.label ?? status;
}

function pluralSections(count: number) {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return `${count} раздел`;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} раздела`;
  return `${count} разделов`;
}

function flagTone(enabled: boolean) {
  return enabled ? "success" : "neutral";
}

function normalizeCode(value: string) {
  return value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
}

export function KnowledgeSectionsPage() {
  const queryClient = useQueryClient();
  const spacesQuery = useQuery({ queryKey: ["knowledge-spaces"], queryFn: fetchKnowledgeSpaces });
  const spaces = spacesQuery.data ?? [];
  const [search, setSearch] = useState("");
  const [selectedSpaceId, setSelectedSpaceId] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [draft, setDraft] = useState<SectionDraft>(() => emptyDraft());
  const [saveMessage, setSaveMessage] = useState("");

  const spacesKey = spaces.map((space) => `${space.space_id}:${space.code}:${space.updated_at ?? ""}`).join("|");
  const selectedSpace = spaces.find((space) => space.space_id === selectedSpaceId) ?? spaces[0] ?? null;
  const selectedSignature = selectedSpace
    ? `${selectedSpace.space_id}:${selectedSpace.code}:${selectedSpace.title}:${selectedSpace.visibility}:${selectedSpace.lifecycle_status}:${selectedSpace.allow_publication}:${selectedSpace.allow_ingestion}:${selectedSpace.allow_rag}`
    : "";

  useEffect(() => {
    if (!isCreating && !selectedSpaceId && spaces[0]?.space_id) {
      setSelectedSpaceId(spaces[0].space_id);
    }
  }, [isCreating, selectedSpaceId, spacesKey, spaces]);

  useEffect(() => {
    setDraft(draftFromSpace(isCreating ? null : selectedSpace));
    setSaveMessage("");
  }, [isCreating, selectedSignature]);

  const filteredSpaces = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) {
      return spaces;
    }
    return spaces.filter((space) =>
      [space.title, space.code, space.description, space.visibility, space.lifecycle_status].some((value) =>
        String(value ?? "").toLowerCase().includes(needle),
      ),
    );
  }, [search, spaces]);

  const saveMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeSpace({
        allow_ingestion: draft.allow_ingestion,
        allow_publication: draft.allow_publication,
        allow_rag: draft.allow_rag,
        code: normalizeCode(draft.code),
        description: draft.description.trim() || null,
        lifecycle_status: draft.lifecycle_status,
        title: draft.title.trim(),
        visibility: draft.visibility,
      }),
    onSuccess: (result) => {
      setIsCreating(false);
      setSelectedSpaceId(result.space.space_id);
      setDraft(draftFromSpace(result.space));
      setSaveMessage("Раздел сохранен");
      queryClient.invalidateQueries({ queryKey: ["knowledge-spaces"] });
    },
  });

  const canSave = normalizeCode(draft.code).length > 0 && draft.title.trim().length > 0;

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <Button
            leadingIcon={<Plus className="h-4 w-4" />}
            onClick={() => {
              setIsCreating(true);
              setSelectedSpaceId("");
            }}
            title="Создать новый раздел базы знаний"
            variant="secondary"
          >
            Новый раздел
          </Button>
        }
        eyebrow="Knowledge Section Constructor"
        title="Разделы базы знаний"
        description="Единое место для политики раздела: видимость по умолчанию, импорт, публикация, RAG и аудитория без ручного JSON."
      />

      <nav aria-label="Разделы платформы знаний" className="flex flex-wrap gap-2">
        {domainTabs.map((tab) => (
          <a
            aria-current={tab.active ? "page" : undefined}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium ${
              tab.active ? "border-brand-200 bg-brand-50 text-brand-800" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
            href={tab.href}
            key={tab.href}
          >
            {tab.label}
          </a>
        ))}
      </nav>

      <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section className="surface-panel p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-slate-950">Список разделов</h2>
              <p className="mt-1 text-sm text-slate-500">{pluralSections(filteredSpaces.length)}</p>
            </div>
            <FolderKanban className="h-5 w-5 text-brand-700" />
          </div>
          <label className="mt-4 block text-sm font-medium text-slate-700">
            Поиск раздела
            <input
              className={fieldClass}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Название, код или статус"
              title="Фильтрует список разделов по названию, коду, статусу и видимости"
              value={search}
            />
          </label>

          <div className="mt-4 space-y-2">
            {spacesQuery.isLoading ? <p className="text-sm text-slate-500">Загрузка разделов...</p> : null}
            {filteredSpaces.map((space) => {
              const active = !isCreating && selectedSpace?.space_id === space.space_id;
              return (
                <button
                  aria-pressed={active}
                  className={`w-full rounded-md border p-3 text-left transition-colors ${
                    active ? "border-brand-300 bg-brand-50" : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                  }`}
                  key={space.space_id}
                  onClick={() => {
                    setIsCreating(false);
                    setSelectedSpaceId(space.space_id);
                  }}
                  type="button"
                >
                  <span className="flex items-start justify-between gap-2">
                    <span>
                      <span className="block text-sm font-semibold text-slate-950">{space.title}</span>
                      <span className="mt-1 block text-xs text-slate-500">{space.code}</span>
                    </span>
                    <Badge tone={space.lifecycle_status === "active" ? "success" : "neutral"}>{statusLabel(space.lifecycle_status)}</Badge>
                  </span>
                  <span className="mt-3 flex flex-wrap gap-2">
                    <Badge tone="brand">{visibilityLabels[space.visibility] ?? space.visibility}</Badge>
                    <Badge tone={flagTone(space.allow_rag ?? true)}>{space.allow_rag ?? true ? "Используется в AI/RAG" : "AI/RAG выключен"}</Badge>
                    <Badge tone={flagTone(space.allow_ingestion ?? true)}>{space.allow_ingestion ?? true ? "Импорт разрешен" : "Импорт закрыт"}</Badge>
                    <Badge tone={flagTone(space.allow_publication ?? true)}>{space.allow_publication ?? true ? "Публикация разрешена" : "Публикация закрыта"}</Badge>
                  </span>
                </button>
              );
            })}
            {!spacesQuery.isLoading && filteredSpaces.length === 0 ? (
              <p className="rounded-md border border-dashed border-slate-200 p-4 text-sm text-slate-500">Разделы не найдены.</p>
            ) : null}
          </div>
        </section>

        <div className="space-y-4">
          <section className="surface-panel p-4" data-testid="section-policy-editor">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">Политика раздела</h2>
                <p className="mt-1 text-sm text-slate-500">
                  Настройки применяются как значения по умолчанию для статей, импорта, публикации и RAG-подготовки.
                </p>
              </div>
              <Badge tone={isCreating ? "warning" : "brand"}>{isCreating ? "Новый раздел" : selectedSpace?.code ?? "Раздел"}</Badge>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <label className="text-sm font-medium text-slate-700">
                Название раздела
                <input
                  className={fieldClass}
                  onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
                  placeholder="Например, IT Self-Service"
                  title="Понятное название раздела для администраторов и авторов"
                  value={draft.title}
                />
              </label>
              <label className="text-sm font-medium text-slate-700">
                Код раздела
                <input
                  className={`${fieldClass} disabled:bg-slate-50 disabled:text-slate-500`}
                  disabled={!isCreating}
                  onChange={(event) => setDraft((current) => ({ ...current, code: normalizeCode(event.target.value) }))}
                  placeholder="it-self-service"
                  title={isCreating ? "Стабильный код раздела для связей и импорта" : "Код существующего раздела не переименовывается этим экраном"}
                  value={draft.code}
                />
              </label>
              <label className="text-sm font-medium text-slate-700">
                Видимость по умолчанию
                <select
                  className={fieldClass}
                  onChange={(event) => setDraft((current) => ({ ...current, visibility: event.target.value }))}
                  title="Грубая область видимости для новых статей раздела"
                  value={draft.visibility}
                >
                  {visibilityOptions.map((value) => (
                    <option key={value} value={value}>
                      {visibilityLabels[value] ?? value}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700">
                Статус раздела
                <select
                  className={fieldClass}
                  onChange={(event) => setDraft((current) => ({ ...current, lifecycle_status: event.target.value }))}
                  title="Архивный раздел остается в базе, но исключается из рабочих сценариев"
                  value={draft.lifecycle_status}
                >
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm font-medium text-slate-700 lg:col-span-2">
                Описание
                <textarea
                  className={`${fieldClass} min-h-24`}
                  onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
                  placeholder="Для каких материалов и процессов используется раздел"
                  title="Описание помогает авторам выбрать правильный раздел"
                  value={draft.description}
                />
              </label>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              <label className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <input
                  checked={draft.allow_rag}
                  className={checkboxClass}
                  onChange={(event) => setDraft((current) => ({ ...current, allow_rag: event.target.checked }))}
                  title="Разрешает использовать материалы раздела в RAG и поисковой подготовке"
                  type="checkbox"
                />
                <span>
                  <span className="block font-semibold text-slate-900">Использовать в AI/RAG</span>
                  <span className="mt-1 block text-xs text-slate-500">Материалы участвуют в retrieval и ответах AI.</span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <input
                  checked={draft.allow_ingestion}
                  className={checkboxClass}
                  onChange={(event) => setDraft((current) => ({ ...current, allow_ingestion: event.target.checked }))}
                  title="Разрешает импортировать новые материалы в этот раздел"
                  type="checkbox"
                />
                <span>
                  <span className="block font-semibold text-slate-900">Разрешить импорт</span>
                  <span className="mt-1 block text-xs text-slate-500">Импорт может создавать review draft в разделе.</span>
                </span>
              </label>
              <label className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <input
                  checked={draft.allow_publication}
                  className={checkboxClass}
                  onChange={(event) => setDraft((current) => ({ ...current, allow_publication: event.target.checked }))}
                  title="Разрешает публикацию статей раздела"
                  type="checkbox"
                />
                <span>
                  <span className="block font-semibold text-slate-900">Разрешить публикацию</span>
                  <span className="mt-1 block text-xs text-slate-500">Авторы могут переводить статьи раздела в published.</span>
                </span>
              </label>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Button
                disabled={!canSave || saveMutation.isPending}
                leadingIcon={<Save className="h-4 w-4" />}
                onClick={() => saveMutation.mutate()}
                title="Сохранить политику раздела"
              >
                Сохранить раздел
              </Button>
              {saveMessage ? <p className="text-sm font-medium text-emerald-700">{saveMessage}</p> : null}
              {saveMutation.isError ? <p className="text-sm font-medium text-rose-700">Не удалось сохранить раздел.</p> : null}
            </div>
          </section>

          <SectionAudiencePanel canManage={!isCreating} coarseVisibility={draft.visibility} space={isCreating ? null : selectedSpace} />
        </div>
      </div>
    </section>
  );
}

type SectionAudiencePanelProps = {
  canManage: boolean;
  coarseVisibility: string;
  space: KnowledgeSpace | null;
};

function SectionAudiencePanel({ canManage, coarseVisibility, space }: SectionAudiencePanelProps) {
  const queryClient = useQueryClient();
  const [draftRules, setDraftRules] = useState<KnowledgeAudienceRuleInput[]>([]);
  const [targetType, setTargetType] = useState<KnowledgeAudienceRuleTargetType>("department_tree");
  const [targetId, setTargetId] = useState("");
  const [actorId, setActorId] = useState("");
  const [reason, setReason] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [previewResult, setPreviewResult] = useState<KnowledgeAudiencePreview | null>(null);

  const subjectId = space?.space_id ?? "";
  const rulesQuery = useQuery({
    queryKey: ["knowledge-audience-rules", "space", subjectId],
    queryFn: () => fetchKnowledgeAudienceRules("space", subjectId),
    enabled: Boolean(subjectId),
  });
  const lookupsQuery = useQuery({
    queryKey: ["knowledge-visibility-lookups"],
    queryFn: fetchVisibilityLookups,
    enabled: Boolean(subjectId),
  });

  const rulesKey = (rulesQuery.data ?? []).map((rule) => `${rule.rule_id ?? ""}:${rule.updated_at ?? ""}:${rule.target_type}:${rule.target_id}`).join("|");
  useEffect(() => {
    if (!subjectId) {
      setDraftRules([]);
      setPreviewResult(null);
      return;
    }
    if (rulesQuery.data) {
      setDraftRules(rulesQuery.data.map(ruleToDraft));
      setPreviewResult(null);
    }
  }, [rulesKey, subjectId, rulesQuery.data]);

  useEffect(() => {
    setSaveMessage("");
    setReason("");
  }, [subjectId]);

  const targetOptions = useMemo(() => targetOptionsFor(targetType, lookupsQuery.data), [lookupsQuery.data, targetType]);
  const targetOptionsKey = targetOptions.map((option) => option.value).join("|");
  useEffect(() => {
    if (!targetOptions.length) {
      setTargetId("");
      return;
    }
    if (!targetOptions.some((option) => option.value === targetId)) {
      setTargetId(targetOptions[0]?.value ?? "");
    }
  }, [targetOptionsKey, targetType, targetId, targetOptions]);

  const audienceEstimate = useMemo(() => estimateAudience(draftRules, lookupsQuery.data), [draftRules, lookupsQuery.data]);
  const broadWarning = draftRules.length === 0 && ["public", "requester", "agent_requester_safe"].includes(coarseVisibility);
  const emptyWarning = draftRules.length > 0 && audienceEstimate.count === 0;
  const internalWarning = internalVisibilityWarning(coarseVisibility);

  const previewMutation = useMutation({
    mutationFn: () =>
      previewKnowledgeAudienceRules({
        subject_type: "space",
        subject_id: subjectId,
        actor_id: actorId.trim() || null,
        actor_role: "user",
        rules: draftRules,
      }),
    onSuccess: setPreviewResult,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      replaceKnowledgeAudienceRules({
        subject_type: "space",
        subject_id: subjectId,
        rules: draftRules,
        reason: reason.trim() || null,
      }),
    onSuccess: (rules) => {
      setDraftRules(rules.map(ruleToDraft));
      queryClient.setQueryData(["knowledge-audience-rules", "space", subjectId], rules);
      setSaveMessage("Аудитория раздела сохранена");
    },
  });

  function addRule() {
    if (!targetId) return;
    setDraftRules((current) => [
      ...current,
      {
        effect: "allow",
        include_children: targetType === "department_tree",
        metadata_json: {},
        priority: (current.length + 1) * 10,
        reason: reason.trim() || null,
        status: "active",
        target_id: targetId,
        target_type: targetType,
      },
    ]);
    setPreviewResult(null);
  }

  function removeRule(index: number) {
    setDraftRules((current) => current.filter((_rule, ruleIndex) => ruleIndex !== index));
    setPreviewResult(null);
  }

  return (
    <section className="surface-panel p-4" data-testid="section-audience-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">Аудитория раздела</h2>
          <p className="mt-1 text-sm text-slate-500">
            Правила раздела становятся контрактом видимости для статей и RAG-выдачи внутри выбранного раздела.
          </p>
        </div>
        <Badge tone="brand">{space ? visibilityLabels[coarseVisibility] ?? coarseVisibility : "Сначала сохраните раздел"}</Badge>
      </div>

      {!space ? (
        <p className="mt-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Сохраните новый раздел, чтобы настроить аудиторию на стабильном идентификаторе раздела.
        </p>
      ) : null}

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="space-y-3">
          {rulesQuery.isLoading || lookupsQuery.isLoading ? <p className="text-sm text-slate-500">Загрузка правил и справочников...</p> : null}
          {internalWarning ? (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Внутренний раздел не станет видимым заявителям только за счет правил аудитории.
            </p>
          ) : null}
          {broadWarning ? (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Нет правил аудитории: раздел наследует широкую аудиторию грубой области видимости.
            </p>
          ) : null}
          {emptyWarning ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              Правила не находят активных людей в Registry. Проверьте подразделения, группы и архивные записи.
            </p>
          ) : null}

          <div className="space-y-2">
            {draftRules.map((rule, index) => (
              <div
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
                key={`${rule.target_type}:${rule.target_id}:${index}`}
              >
                <div>
                  <p className="font-medium text-slate-900">{ruleLabel(rule, lookupsQuery.data)}</p>
                  <p className="text-xs text-slate-500">
                    allow · priority {rule.priority ?? (index + 1) * 10}
                    {rule.reason ? ` · ${rule.reason}` : ""}
                  </p>
                </div>
                <Button
                  aria-label={`Удалить правило ${ruleLabel(rule, lookupsQuery.data)}`}
                  disabled={!canManage}
                  leadingIcon={<Trash2 className="h-4 w-4" />}
                  onClick={() => removeRule(index)}
                  size="sm"
                  title="Удалить правило из черновика аудитории"
                  variant="ghost"
                >
                  Удалить
                </Button>
              </div>
            ))}
            {!draftRules.length ? <p className="text-sm text-slate-500">Правил аудитории пока нет.</p> : null}
          </div>
        </div>

        <aside className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="font-semibold text-slate-950">Оценка аудитории: {pluralPeople(audienceEstimate.count)}</p>
          {audienceEstimate.matchedLabels.length ? (
            <ul className="mt-2 space-y-1 text-slate-600">
              {audienceEstimate.matchedLabels.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-slate-500">Выберите правила, чтобы увидеть совпавшие подразделения и группы.</p>
          )}
        </aside>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[180px_minmax(0,1fr)_auto]">
        <label className="text-sm font-medium text-slate-700">
          Тип правила
          <select
            className={fieldClass}
            disabled={!canManage}
            onChange={(event) => setTargetType(event.target.value as KnowledgeAudienceRuleTargetType)}
            title="Тип Registry-объекта, который получает доступ к разделу"
            value={targetType}
          >
            {targetTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium text-slate-700">
          Значение правила
          <select
            className={fieldClass}
            disabled={!canManage || !targetOptions.length}
            onChange={(event) => setTargetId(event.target.value)}
            title="Конкретное подразделение, группа, роль или другой объект Registry"
            value={targetId}
          >
            {targetOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
                {option.secondary ? ` · ${option.secondary}` : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-end">
          <Button disabled={!canManage || !targetId} onClick={addRule} title="Добавить правило в черновик аудитории" variant="secondary">
            Добавить правило
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="text-sm font-medium text-slate-700">
          Пользователь для проверки
          <input
            className={fieldClass}
            disabled={!space}
            onChange={(event) => setActorId(event.target.value)}
            placeholder="login@example.test"
            title="Логин или email пользователя для серверного предпросмотра"
            value={actorId}
          />
        </label>
        <label className="text-sm font-medium text-slate-700">
          Причина изменения
          <input
            className={fieldClass}
            disabled={!space}
            onChange={(event) => setReason(event.target.value)}
            title="Попадает в audit trail изменения правил"
            value={reason}
          />
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <Button
            disabled={!space || previewMutation.isPending}
            leadingIcon={<Eye className="h-4 w-4" />}
            onClick={() => previewMutation.mutate()}
            size="sm"
            title="Проверить текущий черновик правил на сервере"
            variant="outline"
          >
            Предпросмотр аудитории
          </Button>
        </div>
      </div>

      {previewResult ? (
        <p className={`mt-3 rounded-md px-3 py-2 text-sm font-medium ${previewResult.decision.allowed ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>
          {decisionLabel(previewResult)} · Причина решения: {previewResult.decision.reason_code}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled={!canManage || !space || saveMutation.isPending} onClick={() => saveMutation.mutate()} title="Сохранить правила аудитории раздела">
          Сохранить аудиторию
        </Button>
        {saveMessage ? <p className="text-sm font-medium text-emerald-700">{saveMessage}</p> : null}
        {rulesQuery.isError || lookupsQuery.isError || previewMutation.isError || saveMutation.isError ? (
          <p className="text-sm font-medium text-rose-700">Не удалось выполнить действие с аудиторией раздела.</p>
        ) : null}
      </div>
    </section>
  );
}
