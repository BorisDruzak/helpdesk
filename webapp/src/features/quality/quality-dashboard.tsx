import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { formatRussianDateTime } from "../../components/ui-page";
import { qualityLabel } from "./labels";
import {
  closeImprovementAction,
  completeQualityReview,
  createImprovementAction,
  fetchImprovementActions,
  fetchQualityPolicy,
  fetchQualityReviews,
  fetchQualitySummary,
  fetchServiceQuality,
  saveQualityPolicy,
} from "./api";

function metric(value: number | null | undefined, suffix = "") {
  if (value === null || value === undefined) {
    return "Нет данных";
  }
  return `${value}${suffix}`;
}

export function QualityDashboard() {
  const queryClient = useQueryClient();
  const [actionTitle, setActionTitle] = useState("");
  const [actionOwner, setActionOwner] = useState("");
  const [policyServiceCode, setPolicyServiceCode] = useState("");
  const [policyOfferingCode, setPolicyOfferingCode] = useState("");
  const [policyThreshold, setPolicyThreshold] = useState(3);
  const summaryQuery = useQuery({ queryKey: ["quality", "summary"], queryFn: fetchQualitySummary });
  const serviceQualityQuery = useQuery({ queryKey: ["quality", "service-quality"], queryFn: fetchServiceQuality });
  const reviewsQuery = useQuery({ queryKey: ["quality", "reviews"], queryFn: () => fetchQualityReviews() });
  const actionsQuery = useQuery({ queryKey: ["quality", "actions"], queryFn: () => fetchImprovementActions() });
  const policyQuery = useQuery({
    queryKey: ["quality", "policy", policyServiceCode, policyOfferingCode],
    queryFn: () =>
      fetchQualityPolicy({
        serviceCode: policyServiceCode.trim() || null,
        offeringCode: policyOfferingCode.trim() || null,
      }),
  });

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["quality", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "service-quality"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "reviews"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "actions"] }),
      queryClient.invalidateQueries({ queryKey: ["quality", "policy"] }),
    ]);
  };

  const createActionMutation = useMutation({
    mutationFn: () =>
      createImprovementAction({
        source_kind: "manual",
        action_type: "process_review",
        title: actionTitle.trim(),
        description: actionTitle.trim(),
        priority: "medium",
        owner_actor_id: actionOwner.trim() || null,
      }),
    onSuccess: async () => {
      setActionTitle("");
      setActionOwner("");
      await invalidate();
    },
  });

  const completeReviewMutation = useMutation({
    mutationFn: (reviewId: string) => completeQualityReview(reviewId, 85),
    onSuccess: invalidate,
  });

  const closeActionMutation = useMutation({
    mutationFn: (actionId: string) => closeImprovementAction(actionId, "Завершено в разделе качества."),
    onSuccess: invalidate,
  });

  const savePolicyMutation = useMutation({
    mutationFn: () =>
      saveQualityPolicy({
        scope_type: policyOfferingCode.trim() ? "offering" : policyServiceCode.trim() ? "service" : "global",
        service_code: policyServiceCode.trim() || null,
        offering_code: policyOfferingCode.trim() || null,
        enabled: true,
        low_csat_threshold: policyThreshold,
        reopen_review_enabled: policy?.reopen_review_enabled ?? true,
        sla_breach_review_enabled: policy?.sla_breach_review_enabled ?? true,
        high_priority_review_enabled: policy?.high_priority_review_enabled ?? true,
        missing_evidence_review_enabled: policy?.missing_evidence_review_enabled ?? true,
        random_sample_percent: policy?.random_sample_percent ?? 0,
        qa_due_hours: policy?.qa_due_hours ?? 72,
      }),
    onSuccess: invalidate,
  });

  const summary = summaryQuery.data;
  const policy = policyQuery.data;

  useEffect(() => {
    if (policy?.low_csat_threshold) {
      setPolicyThreshold(policy.low_csat_threshold);
    }
  }, [policy?.low_csat_threshold]);

  return (
    <section className="workspace-page grid gap-5">
      <div className="workspace-page__header">
        <div>
          <p className="workspace-boot__eyebrow">Качество обслуживания</p>
          <h1>Управление качеством</h1>
          <p>Оценки пользователей, причины повторных обращений, проверки качества и задачи по улучшению обслуживания.</p>
        </div>
        <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void invalidate()} type="button" variant="outline">
          Обновить
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Средняя оценка пользователей</CardDescription>
            <CardTitle>{metric(summary?.avg_csat)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Оценки пользователей</CardDescription>
            <CardTitle>{metric(summary?.feedback_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Повторные открытия</CardDescription>
            <CardTitle>{metric(summary?.reopen_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Открытые задачи улучшения</CardDescription>
            <CardTitle>{metric(summary?.improvement_action_count)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Качество услуг</CardTitle>
          <CardDescription>
            Показаны только сводные показатели без персональных данных заявителей и комментариев к оценкам.
            Последний расчёт: {formatRussianDateTime(serviceQualityQuery.data?.lastComputedAt, { emptyText: "ещё не выполнен" })}.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Услуга</th>
                  <th className="px-3 py-2">Вариант услуги</th>
                  <th className="px-3 py-2">Обращения</th>
                  <th className="px-3 py-2">Оценка пользователей</th>
                  <th className="px-3 py-2">Повторные открытия</th>
                  <th className="px-3 py-2">Нарушения SLA</th>
                  <th className="px-3 py-2">Статья не помогла</th>
                  <th className="px-3 py-2">Не пройдена проверка</th>
                  <th className="px-3 py-2">Задачи улучшения</th>
                </tr>
              </thead>
              <tbody>
                {(serviceQualityQuery.data ?? []).map((row) => (
                  <tr className="border-t border-border" key={`${row.service_code}:${row.offering_code}`}>
                    <td className="px-3 py-2">{row.service_code}</td>
                    <td className="px-3 py-2">{row.offering_code}</td>
                    <td className="px-3 py-2">{row.ticket_count}</td>
                    <td className="px-3 py-2">{metric(row.avg_csat)}</td>
                    <td className="px-3 py-2">{metric(Math.round(row.reopen_rate * 100), "%")}</td>
                    <td className="px-3 py-2">{metric(Math.round(row.sla_breach_rate * 100), "%")}</td>
                    <td className="px-3 py-2">{row.ticket_after_failed_knowledge_count}</td>
                    <td className="px-3 py-2">{row.qa_failed_count}</td>
                    <td className="px-3 py-2">{row.improvement_action_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Очередь проверок качества</CardTitle>
            <CardDescription>Проверки обращений доступны сотрудникам поддержки и администраторам.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {(reviewsQuery.data ?? []).slice(0, 12).map((review) => (
              <div className="rounded-[0.75rem] border border-border px-3 py-3" key={review.review_id}>
                <div className="flex items-center justify-between gap-3">
                  <strong>{qualityLabel(review.review_type)}</strong>
                  <span>{qualityLabel(review.status)}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {qualityLabel(review.severity)} / {review.service_code ?? "Услуга не указана"} / {review.ticket_id}
                </p>
                {["open", "assigned", "in_review"].includes(review.status) ? (
                  <Button className="mt-3" onClick={() => completeReviewMutation.mutate(review.review_id)} size="sm" type="button" variant="outline">
                    Завершить проверку
                  </Button>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Задачи по улучшению</CardTitle>
            <CardDescription>Для каждой задачи указаны ответственный и статус; действия фиксируются в аудите. Заявители эти задачи не видят.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 md:grid-cols-[1fr_180px_auto]">
              <input className="field-base px-3 py-2" onChange={(event) => setActionTitle(event.currentTarget.value)} placeholder="Название задачи" value={actionTitle} />
              <input className="field-base px-3 py-2" onChange={(event) => setActionOwner(event.currentTarget.value)} placeholder="Ответственный" value={actionOwner} />
              <Button disabled={!actionTitle.trim() || createActionMutation.isPending} onClick={() => createActionMutation.mutate()} type="button">
                Создать
              </Button>
            </div>
            {(actionsQuery.data ?? []).slice(0, 12).map((action) => (
              <div className="rounded-[0.75rem] border border-border px-3 py-3" key={action.action_id}>
                <div className="flex items-center justify-between gap-3">
                  <strong>{action.title}</strong>
                  <span>{qualityLabel(action.status)}</span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {qualityLabel(action.priority)} / {qualityLabel(action.action_type)} / Ответственный: {action.owner_actor_id ?? "Не назначен"}
                </p>
                {action.status !== "done" && action.status !== "dismissed" ? (
                  <Button className="mt-3" onClick={() => closeActionMutation.mutate(action.action_id)} size="sm" type="button" variant="outline">
                    Завершить
                  </Button>
                ) : null}
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Правила контроля качества</CardTitle>
          <CardDescription>Просмотр действующих правил и настройка исключений для услуги или её варианта.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 md:grid-cols-[1fr_1fr_140px_auto]">
            <input
              aria-label="Код услуги для правил качества"
              className="field-base px-3 py-2"
              onChange={(event) => setPolicyServiceCode(event.currentTarget.value)}
              placeholder="Код услуги"
              value={policyServiceCode}
            />
            <input
              aria-label="Код варианта услуги для правил качества"
              className="field-base px-3 py-2"
              onChange={(event) => setPolicyOfferingCode(event.currentTarget.value)}
              placeholder="Код варианта услуги"
              value={policyOfferingCode}
            />
            <input
              aria-label="Порог низкой оценки"
              className="field-base px-3 py-2"
              max={5}
              min={1}
              onChange={(event) => setPolicyThreshold(Number(event.currentTarget.value))}
              type="number"
              value={policyThreshold}
            />
            <Button disabled={savePolicyMutation.isPending} onClick={() => savePolicyMutation.mutate()} type="button">
              Сохранить настройки
            </Button>
          </div>
          <div className="grid gap-2 text-sm text-slate-700 md:grid-cols-5">
            <span>Область: {qualityLabel(policy?.scope_type ?? "global")}</span>
            <span>Порог низкой оценки: {policy?.low_csat_threshold ?? "Нет данных"}</span>
            <span>Проверять повторные открытия: {policy?.reopen_review_enabled ? "Да" : "Нет"}</span>
            <span>Проверять нарушения SLA: {policy?.sla_breach_review_enabled ? "Да" : "Нет"}</span>
            <span>Срок проверки, ч: {policy?.qa_due_hours ?? "Нет данных"}</span>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
