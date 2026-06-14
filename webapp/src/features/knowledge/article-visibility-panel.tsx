import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "../../components/ui/button";
import {
  explainKnowledgeAccess,
  fetchKnowledgeAudienceRules,
  previewKnowledgeAudienceRules,
  replaceKnowledgeAudienceRules,
  type KnowledgeAudienceExplain,
  type KnowledgeAudiencePreview,
  type KnowledgeAudienceRuleInput,
  type KnowledgeAudienceRuleTargetType,
  type KnowledgeItem,
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

type ArticleVisibilityPanelProps = {
  canManage?: boolean;
  coarseVisibility: string;
  item: KnowledgeItem | null;
};

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900";

export function ArticleVisibilityPanel({ canManage = true, coarseVisibility, item }: ArticleVisibilityPanelProps) {
  const queryClient = useQueryClient();
  const [draftRules, setDraftRules] = useState<KnowledgeAudienceRuleInput[]>([]);
  const [targetType, setTargetType] = useState<KnowledgeAudienceRuleTargetType>("department_tree");
  const [targetId, setTargetId] = useState("");
  const [actorId, setActorId] = useState("");
  const [reason, setReason] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [previewResult, setPreviewResult] = useState<KnowledgeAudiencePreview | null>(null);
  const [explainResult, setExplainResult] = useState<KnowledgeAudienceExplain | null>(null);

  const subjectId = item?.item_id ?? "";
  const rulesQuery = useQuery({
    queryKey: ["knowledge-audience-rules", "item", subjectId],
    queryFn: () => fetchKnowledgeAudienceRules("item", subjectId),
    enabled: Boolean(subjectId),
  });
  const lookupsQuery = useQuery({
    queryKey: ["knowledge-visibility-lookups"],
    queryFn: fetchVisibilityLookups,
    enabled: Boolean(subjectId),
  });

  const rulesKey = (rulesQuery.data ?? []).map((rule) => `${rule.rule_id ?? ""}:${rule.updated_at ?? ""}:${rule.target_type}:${rule.target_id}`).join("|");
  useEffect(() => {
    if (rulesQuery.data) {
      setDraftRules(rulesQuery.data.map(ruleToDraft));
      setPreviewResult(null);
      setExplainResult(null);
    }
  }, [rulesKey, subjectId]);

  useEffect(() => {
    setSaveMessage("");
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
  }, [targetOptionsKey, targetType, targetId]);

  const audienceEstimate = useMemo(() => estimateAudience(draftRules, lookupsQuery.data), [draftRules, lookupsQuery.data]);
  const broadWarning = draftRules.length === 0 && ["public", "requester", "agent_requester_safe"].includes(coarseVisibility);
  const emptyWarning = draftRules.length > 0 && audienceEstimate.count === 0;
  const internalWarning = internalVisibilityWarning(coarseVisibility);

  const previewMutation = useMutation({
    mutationFn: () =>
      previewKnowledgeAudienceRules({
        subject_type: "item",
        subject_id: subjectId,
        actor_id: actorId.trim() || null,
        actor_role: "user",
        rules: draftRules,
      }),
    onSuccess: setPreviewResult,
  });

  const explainMutation = useMutation({
    mutationFn: () =>
      explainKnowledgeAccess({
        item_id: subjectId,
        actor_id: actorId.trim() || null,
        actor_role: "user",
      }),
    onSuccess: setExplainResult,
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      replaceKnowledgeAudienceRules({
        subject_type: "item",
        subject_id: subjectId,
        rules: draftRules,
        reason: reason.trim() || null,
      }),
    onSuccess: (rules) => {
      setDraftRules(rules.map(ruleToDraft));
      queryClient.setQueryData(["knowledge-audience-rules", "item", subjectId], rules);
      setSaveMessage("Правила видимости сохранены");
    },
  });

  function addRule() {
    if (!targetId) return;
    setDraftRules((current) => [
      ...current,
      {
        target_type: targetType,
        target_id: targetId,
        effect: "allow",
        include_children: targetType === "department_tree",
        priority: (current.length + 1) * 10,
        status: "active",
        reason: reason.trim() || null,
        metadata_json: {},
      },
    ]);
    setPreviewResult(null);
    setExplainResult(null);
  }

  function removeRule(index: number) {
    setDraftRules((current) => current.filter((_rule, ruleIndex) => ruleIndex !== index));
    setPreviewResult(null);
    setExplainResult(null);
  }

  if (!item) {
    return (
      <section className="rounded-lg border border-slate-200 bg-slate-50 p-4" data-testid="article-visibility-panel">
        <h3 className="text-base font-semibold text-slate-950">Аудитория</h3>
        <p className="mt-1 text-sm text-slate-500">Выберите статью, чтобы настроить аудиторию без raw JSON.</p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4" data-testid="article-visibility-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Аудитория</h3>
          <p className="mt-1 text-sm text-slate-500">
            Аудитория уточняет доступ внутри выбранной видимости: подразделения, группы, локации, сервисы или отдельные сотрудники.
          </p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-700">
          {visibilityLabels[coarseVisibility] ?? coarseVisibility}
        </span>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_260px]">
        <div className="space-y-3">
          {rulesQuery.isLoading || lookupsQuery.isLoading ? <p className="text-sm text-slate-500">Загрузка правил и справочников...</p> : null}
          {internalWarning ? (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Внутренний материал не станет видимым заявителям из-за правил аудитории.
            </p>
          ) : null}
          {broadWarning ? (
            <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              Нет правил аудитории: материал будет виден всей аудитории грубой области видимости.
            </p>
          ) : null}
          {emptyWarning ? (
            <p className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
              Правила не находят активных людей в Registry. Проверьте выбранные подразделения и группы.
            </p>
          ) : null}

          <div className="space-y-2">
            {draftRules.map((rule, index) => (
              <div key={`${rule.target_type}:${rule.target_id}:${index}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
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
                  onClick={() => removeRule(index)}
                  size="sm"
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
        <label className="text-sm font-medium">
          Тип правила
          <select className={fieldClass} disabled={!canManage} value={targetType} onChange={(event) => setTargetType(event.target.value as KnowledgeAudienceRuleTargetType)}>
            {targetTypeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Значение правила
          <select className={fieldClass} disabled={!canManage || !targetOptions.length} value={targetId} onChange={(event) => setTargetId(event.target.value)}>
            {targetOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
                {option.secondary ? ` · ${option.secondary}` : ""}
              </option>
            ))}
          </select>
        </label>
        <div className="flex items-end">
          <Button disabled={!canManage || !targetId} onClick={addRule} variant="secondary">
            Добавить правило
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="text-sm font-medium">
          Пользователь для проверки
          <input className={fieldClass} placeholder="login@example.test" value={actorId} onChange={(event) => setActorId(event.target.value)} />
        </label>
        <label className="text-sm font-medium">
          Причина изменения
          <input className={fieldClass} value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <Button disabled={!subjectId || previewMutation.isPending} onClick={() => previewMutation.mutate()} size="sm" variant="outline">
            Предпросмотр правил
          </Button>
          <Button disabled={!subjectId || explainMutation.isPending} onClick={() => explainMutation.mutate()} size="sm" variant="outline">
            Проверить доступ
          </Button>
        </div>
      </div>

      {previewResult ? (
        <p className={`mt-3 rounded-md px-3 py-2 text-sm font-medium ${previewResult.decision.allowed ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>
          {decisionLabel(previewResult)} · Причина решения: {previewResult.decision.reason_code}
        </p>
      ) : null}
      {explainResult ? (
        <p className={`mt-3 rounded-md px-3 py-2 text-sm font-medium ${explainResult.decision.allowed ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-800"}`}>
          {decisionLabel(explainResult)} · Причина решения: {explainResult.decision.reason_code}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled={!canManage || saveMutation.isPending} onClick={() => saveMutation.mutate()}>
          Сохранить правила видимости
        </Button>
        {saveMessage ? <p className="text-sm font-medium text-emerald-700">{saveMessage}</p> : null}
        {rulesQuery.isError || lookupsQuery.isError || previewMutation.isError || explainMutation.isError || saveMutation.isError ? (
          <p className="text-sm font-medium text-rose-700">Не удалось выполнить действие с правилами видимости.</p>
        ) : null}
      </div>
    </section>
  );
}
