import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, CheckCircle2, ClipboardCheck, GitPullRequest, RefreshCcw, ShieldAlert } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { fetchServiceCatalogDashboard } from "../service-catalog/api";
import { offeringOptions, serviceOptions } from "../request-template-studio/options";
import {
  approveApproval,
  approvePlan,
  approvePir,
  approveRiskAssessment,
  completeTask,
  createChange,
  createChangeWindow,
  createPir,
  createPlan,
  createRiskAssessment,
  createTask,
  fetchChangeSummary,
  fetchChangeTasks,
  fetchChangeWindows,
  fetchChanges,
  requestApprovals,
  scheduleChange,
  submitRiskAssessment,
  submitPir,
  transitionChange,
  type ChangeApproval,
  type ChangeRecord,
} from "./api";

function valueLabel(value: number | string | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "n/a";
  }
  return String(value);
}

function percentLabel(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${Math.round(value * 100)}%`;
}

function hoursLabel(value: number | null | undefined) {
  if (value === null || value === undefined) {
    return "n/a";
  }
  return `${Math.round(value * 10) / 10}h`;
}

function tone(status: string) {
  if (["closed", "implemented"].includes(status)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-800";
  }
  if (["failed", "rolled_back", "rejected"].includes(status)) {
    return "border-rose-200 bg-rose-50 text-rose-800";
  }
  if (["awaiting_approval", "scheduled", "pir_required"].includes(status)) {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function defaultWindow() {
  const start = new Date(Date.now() + 60 * 60 * 1000);
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  return { planned_start_at: start.toISOString(), planned_end_at: end.toISOString() };
}

export function ChangeWorkspace() {
  const queryClient = useQueryClient();
  const [selectedChangeId, setSelectedChangeId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [changeType, setChangeType] = useState("normal");
  const [serviceCode, setServiceCode] = useState("");
  const [offeringCode, setOfferingCode] = useState("");
  const [latestApprovals, setLatestApprovals] = useState<ChangeApproval[]>([]);

  const summaryQuery = useQuery({ queryKey: ["changes", "summary"], queryFn: fetchChangeSummary });
  const changesQuery = useQuery({ queryKey: ["changes", "list"], queryFn: fetchChanges });
  const windowsQuery = useQuery({ queryKey: ["changes", "windows"], queryFn: fetchChangeWindows });
  const catalogQuery = useQuery({ queryKey: ["changes", "service-catalog-options"], queryFn: fetchServiceCatalogDashboard });
  const changes = changesQuery.data ?? [];
  const servicePickerOptions = serviceOptions(catalogQuery.data?.services ?? []);
  const offeringPickerOptions = offeringOptions(catalogQuery.data?.offerings ?? [], serviceCode);
  const selectedChange = useMemo<ChangeRecord | null>(
    () => changes.find((change) => change.change_id === selectedChangeId) ?? changes[0] ?? null,
    [changes, selectedChangeId],
  );
  const tasksQuery = useQuery({
    enabled: Boolean(selectedChange?.change_id),
    queryKey: ["changes", "tasks", selectedChange?.change_id],
    queryFn: () => fetchChangeTasks(selectedChange?.change_id ?? ""),
  });

  useEffect(() => {
    if (!selectedChangeId && changes[0]) {
      setSelectedChangeId(changes[0].change_id);
    }
  }, [changes, selectedChangeId]);

  const invalidate = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["changes", "summary"] }),
      queryClient.invalidateQueries({ queryKey: ["changes", "list"] }),
      queryClient.invalidateQueries({ queryKey: ["changes", "windows"] }),
      queryClient.invalidateQueries({ queryKey: ["changes", "tasks"] }),
    ]);
  };

  const createMutation = useMutation({
    mutationFn: () =>
      createChange({
        title: title.trim(),
        description: title.trim(),
        change_type: changeType,
        service_code: serviceCode.trim() || null,
        offering_code: offeringCode.trim() || null,
        emergency_justification: changeType === "emergency" ? "Emergency change justification recorded in P5 workspace." : null,
      }),
    onSuccess: async (change) => {
      setSelectedChangeId(change.change_id);
      setTitle("");
      await invalidate();
    },
  });
  const riskMutation = useMutation({
    mutationFn: async (changeId: string) => {
      const risk = await createRiskAssessment(changeId);
      await submitRiskAssessment(changeId, risk.assessment_id);
      return approveRiskAssessment(changeId, risk.assessment_id);
    },
    onSuccess: invalidate,
  });
  const planMutation = useMutation({
    mutationFn: async (changeId: string) => {
      const plan = await createPlan(changeId);
      return approvePlan(changeId, plan.plan_id);
    },
    onSuccess: invalidate,
  });
  const approvalMutation = useMutation({
    mutationFn: (changeId: string) => requestApprovals(changeId),
    onSuccess: async (result) => {
      setLatestApprovals(result.approvals);
      await invalidate();
    },
  });
  const approvalDecisionMutation = useMutation({
    mutationFn: (payload: { changeId: string; approvalId: string }) => approveApproval(payload.changeId, payload.approvalId),
    onSuccess: invalidate,
  });
  const windowMutation = useMutation({
    mutationFn: () => {
      const window = defaultWindow();
      return createChangeWindow({ title: "P5 maintenance window", window_type: "maintenance", starts_at: window.planned_start_at, ends_at: window.planned_end_at });
    },
    onSuccess: invalidate,
  });
  const scheduleMutation = useMutation({
    mutationFn: (changeId: string) => scheduleChange(changeId, defaultWindow()),
    onSuccess: invalidate,
  });
  const taskMutation = useMutation({ mutationFn: (changeId: string) => createTask(changeId), onSuccess: invalidate });
  const completeTaskMutation = useMutation({
    mutationFn: (payload: { changeId: string; taskId: string }) => completeTask(payload.changeId, payload.taskId),
    onSuccess: invalidate,
  });
  const transitionMutation = useMutation({
    mutationFn: (payload: { changeId: string; status: string }) =>
      transitionChange(payload.changeId, {
        status: payload.status,
        closure_summary: "Change closed after PIR approval.",
        rollback_summary: "Rollback outcome recorded.",
        override: payload.status === "implemented",
      }),
    onSuccess: invalidate,
  });
  const pirMutation = useMutation({
    mutationFn: async (changeId: string) => {
      const pir = await createPir(changeId);
      await submitPir(changeId, pir.pir_id);
      return approvePir(changeId, pir.pir_id);
    },
    onSuccess: invalidate,
  });

  const summary = summaryQuery.data;
  const tasks = tasksQuery.data ?? [];

  return (
    <section className="workspace-page grid gap-5">
      <div className="workspace-page__header">
        <div>
          <p className="workspace-boot__eyebrow">Управление изменениями</p>
          <h1>Рабочее место изменений</h1>
          <p>Риски, согласования, окна работ, задачи внедрения, откат и PIR для постоянных исправлений.</p>
        </div>
        <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void invalidate()} type="button" variant="outline">
          Обновить
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader>
            <CardDescription>Всего изменений</CardDescription>
            <CardTitle>{valueLabel(summary?.change_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Открыто</CardDescription>
            <CardTitle>{valueLabel(summary?.open_change_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Аварийные</CardDescription>
            <CardTitle>{valueLabel(summary?.emergency_change_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>С ошибкой</CardDescription>
            <CardTitle>{valueLabel(summary?.failed_change_count)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Завершение PIR</CardDescription>
            <CardTitle>{percentLabel(summary?.pir_completion_rate)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Доля ошибок</CardDescription>
            <CardTitle>{percentLabel(summary?.failure_rate)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Доля откатов</CardDescription>
            <CardTitle>{percentLabel(summary?.rollback_rate)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Время подготовки</CardDescription>
            <CardTitle>{hoursLabel(summary?.average_lead_time_hours)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Просрочен разбор аварий</CardDescription>
            <CardTitle>{valueLabel(summary?.emergency_retrospective_overdue_count)}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Запросы на изменение</CardTitle>
            <CardDescription>Отдельные изменения, не тикеты, с типом и состоянием управления.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-2 md:grid-cols-2 2xl:grid-cols-[minmax(220px,1fr)_150px_minmax(180px,1fr)_minmax(200px,1fr)_auto]">
              <input className="field-base px-3 py-2" onChange={(event) => setTitle(event.currentTarget.value)} placeholder="Название изменения" value={title} />
              <select className="field-base px-3 py-2" onChange={(event) => setChangeType(event.currentTarget.value)} value={changeType}>
                <option value="standard">Стандартное</option>
                <option value="normal">Обычное</option>
                <option value="emergency">Аварийное</option>
              </select>
              <select
                className="field-base px-3 py-2"
                disabled={catalogQuery.isLoading || catalogQuery.isError || servicePickerOptions.length === 0}
                onChange={(event) => {
                  setServiceCode(event.currentTarget.value);
                  setOfferingCode("");
                }}
                value={serviceCode}
              >
                <option value="">{catalogQuery.isLoading ? "Загрузка услуг..." : "Услуга не выбрана"}</option>
                {servicePickerOptions.map((option) => (
                  <option disabled={option.disabled} key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <select
                className="field-base px-3 py-2"
                disabled={!serviceCode || catalogQuery.isLoading || catalogQuery.isError || offeringPickerOptions.length === 0}
                onChange={(event) => setOfferingCode(event.currentTarget.value)}
                value={offeringCode}
              >
                <option value="">{serviceCode ? "Вариант услуги не выбран" : "Сначала выберите услугу"}</option>
                {offeringPickerOptions.map((option) => (
                  <option disabled={option.disabled} key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <Button disabled={!title.trim() || createMutation.isPending} leadingIcon={<GitPullRequest className="h-4 w-4" />} onClick={() => createMutation.mutate()} type="button">
                Создать
              </Button>
            </div>
            {catalogQuery.isError ? (
              <p className="text-sm text-amber-700">Каталог услуг недоступен. Можно создать изменение без привязки и заполнить связь позже.</p>
            ) : null}
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Ключ</th>
                    <th className="px-3 py-2">Название</th>
                    <th className="px-3 py-2">Тип</th>
                    <th className="px-3 py-2">Статус</th>
                    <th className="px-3 py-2">Риск</th>
                    <th className="px-3 py-2">Услуга</th>
                  </tr>
                </thead>
                <tbody>
                  {changes.map((change) => (
                    <tr
                      className={selectedChange?.change_id === change.change_id ? "bg-brand-50" : "hover:bg-slate-50"}
                      key={change.change_id}
                      onClick={() => setSelectedChangeId(change.change_id)}
                    >
                      <td className="px-3 py-2 font-mono text-xs">{change.change_key}</td>
                      <td className="px-3 py-2 font-medium">{change.title}</td>
                      <td className="px-3 py-2">{change.change_type}</td>
                      <td className="px-3 py-2">
                        <span className={`rounded border px-2 py-1 text-xs ${tone(change.status)}`}>{change.status}</span>
                      </td>
                      <td className="px-3 py-2">{change.risk_level}</td>
                      <td className="px-3 py-2">{change.service_code ?? "legacy"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {changes.length === 0 ? <p className="px-3 py-6 text-sm text-slate-500">Изменений пока нет.</p> : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Selected change</CardTitle>
            <CardDescription>Approval path, maintenance window, implementation tasks and PIR.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {selectedChange ? (
              <>
                <div>
                  <p className="font-mono text-xs text-slate-500">{selectedChange.change_key}</p>
                  <h2 className="text-lg font-semibold text-slate-950">{selectedChange.title}</h2>
                  <p className="text-sm text-slate-500">
                    {selectedChange.change_type} / {selectedChange.status} / {selectedChange.risk_level}
                  </p>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Button leadingIcon={<ShieldAlert className="h-4 w-4" />} onClick={() => riskMutation.mutate(selectedChange.change_id)} type="button" variant="outline">
                    Согласовать риск
                  </Button>
                  <Button leadingIcon={<ClipboardCheck className="h-4 w-4" />} onClick={() => planMutation.mutate(selectedChange.change_id)} type="button" variant="outline">
                    Согласовать план
                  </Button>
                  <Button onClick={() => approvalMutation.mutate(selectedChange.change_id)} type="button" variant="outline">
                    Запросить согласование
                  </Button>
                  <Button
                    disabled={!latestApprovals.find((approval) => approval.change_id === selectedChange.change_id && approval.status === "pending")}
                    onClick={() => {
                      const approval = latestApprovals.find((item) => item.change_id === selectedChange.change_id && item.status === "pending");
                      if (approval) {
                        approvalDecisionMutation.mutate({ changeId: selectedChange.change_id, approvalId: approval.approval_id });
                      }
                    }}
                    type="button"
                    variant="outline"
                  >
                    Подтвердить запрос
                  </Button>
                  <Button leadingIcon={<CalendarDays className="h-4 w-4" />} onClick={() => scheduleMutation.mutate(selectedChange.change_id)} type="button" variant="outline">
                    Запланировать
                  </Button>
                  <Button onClick={() => taskMutation.mutate(selectedChange.change_id)} type="button" variant="outline">
                    Добавить задачу
                  </Button>
                  <Button disabled={tasks.length === 0} onClick={() => tasks[0] && completeTaskMutation.mutate({ changeId: selectedChange.change_id, taskId: tasks[0].task_id })} type="button" variant="outline">
                    Завершить задачу
                  </Button>
                  <Button onClick={() => transitionMutation.mutate({ changeId: selectedChange.change_id, status: "implementation_in_progress" })} type="button" variant="outline">
                    Начать
                  </Button>
                  <Button onClick={() => transitionMutation.mutate({ changeId: selectedChange.change_id, status: "implemented" })} type="button" variant="outline">
                    Внедрено
                  </Button>
                  <Button leadingIcon={<CheckCircle2 className="h-4 w-4" />} onClick={() => pirMutation.mutate(selectedChange.change_id)} type="button" variant="outline">
                    PIR
                  </Button>
                  <Button onClick={() => transitionMutation.mutate({ changeId: selectedChange.change_id, status: "closed" })} type="button">
                    Закрыть
                  </Button>
                </div>
                <div className="rounded border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs uppercase text-slate-500">Задачи внедрения</p>
                  <div className="mt-2 space-y-2">
                    {tasks.length ? (
                      tasks.map((task) => (
                        <div className="flex items-center justify-between rounded bg-white px-3 py-2 text-sm" key={task.task_id}>
                          <span>{task.title}</span>
                          <span className="text-xs text-slate-500">{task.status}</span>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">Задач пока нет.</p>
                    )}
                  </div>
                </div>
                <div className="rounded border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs uppercase text-slate-500">Затронутые объекты</p>
                  <p className="mt-1 text-sm text-slate-700">
                    {(selectedChange.affected_objects ?? []).map((item) => item.object_ref).join(", ") || "Связей нет"}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-slate-500">Выберите или создайте изменение.</p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>Календарь изменений</CardTitle>
              <CardDescription>Окна работ и запретов, которые учитываются при планировании изменений.</CardDescription>
            </div>
            <Button leadingIcon={<CalendarDays className="h-4 w-4" />} onClick={() => windowMutation.mutate()} type="button" variant="outline">
              Добавить окно
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {(windowsQuery.data ?? []).map((window) => (
              <div className="rounded border border-slate-200 px-3 py-2 text-sm" key={window.window_id}>
                <p className="font-medium text-slate-950">{window.title}</p>
                <p className="text-xs text-slate-500">
                  {window.window_type} / {new Date(window.starts_at).toLocaleString()} - {new Date(window.ends_at).toLocaleString()}
                </p>
                {window.recurrence_rule ? <p className="text-xs text-slate-500">{window.recurrence_rule}</p> : null}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
