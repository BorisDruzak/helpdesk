import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpenCheck,
  ClipboardCheck,
  FileText,
  Gauge,
  GitBranch,
  PackageCheck,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  UploadCloud,
} from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  createKnowledgeItem,
  createKnowledgeVersion,
  applyKnowledgeContentPack,
  fetchKnowledgeContentPacks,
  fetchKnowledgeGaps,
  fetchKnowledgeItemVersions,
  fetchKnowledgeItems,
  fetchKnowledgeMetricsSummary,
  fetchKnowledgeQuality,
  fetchKnowledgeReviewQueue,
  fetchKnowledgeRolloutPolicies,
  fetchKnowledgeSpaces,
  fetchKnowledgeTemplates,
  publishKnowledgeItem,
  recomputeKnowledgeGaps,
  retireKnowledgeContentPack,
  saveKnowledgeSpace,
  saveKnowledgeRolloutPolicy,
  submitKnowledgeGapAction,
  submitKnowledgeReviewAction,
  submitKnowledgeReviewTaskAction,
  type KnowledgeItem,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";
const textareaClass = `${fieldClass} min-h-36 font-mono text-xs`;

function tone(status: string) {
  if (["published", "active"].includes(status)) {
    return "success" as const;
  }
  if (["draft", "in_review", "needs_review"].includes(status)) {
    return "warning" as const;
  }
  if (["archived", "security_restricted"].includes(status)) {
    return "danger" as const;
  }
  return "neutral" as const;
}

function emptyToNull(value: string | null | undefined) {
  const trimmed = String(value ?? "").trim();
  return trimmed ? trimmed : null;
}

function itemTypeLabel(type: string) {
  const labels: Record<string, string> = {
    article: "Статья",
    faq: "FAQ",
    runbook: "Runbook",
    policy: "Регламент",
    document: "Документ",
    known_error: "Known error",
    workaround: "Workaround",
    troubleshooting_tree: "Troubleshooting tree",
    glossary_term: "Глоссарий",
    service_description: "Описание услуги",
    external_source: "Внешний источник",
    resolution_draft: "Черновик из решения",
  };
  return labels[type] ?? type;
}

function formatDate(value?: string | null) {
  if (!value) {
    return "нет";
  }
  return new Date(value).toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function qualityTone(score: number) {
  if (score >= 80) {
    return "success" as const;
  }
  if (score >= 55) {
    return "warning" as const;
  }
  return "danger" as const;
}

type KnowledgeAdminPanelProps = {
  mode?: "admin" | "support";
};

export function KnowledgeAdminPanel({ mode = "admin" }: KnowledgeAdminPanelProps) {
  const queryClient = useQueryClient();
  const canManage = mode === "admin";
  const canOperate = mode === "admin" || mode === "support";
  const [search, setSearch] = useState("");
  const [selectedItemId, setSelectedItemId] = useState("");
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [reviewNote, setReviewNote] = useState("");
  const [acknowledgeStalePassport, setAcknowledgeStalePassport] = useState(false);
  const [contentPackText, setContentPackText] = useState(
    JSON.stringify(
      {
        code: "it-self-service-baseline",
        version: 1,
        title: "IT Self-Service Baseline",
        spaces: [{ code: "it-self-service", title: "IT Self-Service", visibility: "requester" }],
        items: [],
      },
      null,
      2,
    ),
  );
  const [contentPackForce, setContentPackForce] = useState(false);
  const [contentPackResult, setContentPackResult] = useState("");
  const [reviewActionDraft, setReviewActionDraft] = useState("complete");
  const [rolloutDraft, setRolloutDraft] = useState({
    service_code: "",
    offering_code: "",
    request_template_key: "",
    surface: "requester_portal",
    enabled: true,
    rollout_percent: 100,
    reason: "",
  });
  const [spaceDraft, setSpaceDraft] = useState({
    code: "it-support",
    title: "IT Support",
    visibility: "support_internal",
    lifecycle_status: "active",
    owner_actor_id: "",
    default_reviewer_actor_id: "",
  });
  const [itemDraft, setItemDraft] = useState({
    space_code: "it-support",
    slug: "",
    item_type: "article",
    title: "",
    summary: "",
    visibility: "requester",
    owner_actor_id: "",
    reviewer_actor_id: "",
    service_code: "",
    offering_code: "",
    request_template_key: "",
  });
  const [versionDraft, setVersionDraft] = useState({
    title: "",
    summary: "",
    body_format: "markdown",
    body: "",
    change_summary: "",
  });

  const spacesQuery = useQuery({ queryKey: ["knowledge-spaces"], queryFn: fetchKnowledgeSpaces });
  const itemsQuery = useQuery({ queryKey: ["knowledge-items"], queryFn: fetchKnowledgeItems });
  const metricsQuery = useQuery({ queryKey: ["knowledge-metrics-summary"], queryFn: fetchKnowledgeMetricsSummary });
  const contentPacksQuery = useQuery({ queryKey: ["knowledge-content-packs"], queryFn: fetchKnowledgeContentPacks, enabled: canManage });
  const templatesQuery = useQuery({ queryKey: ["knowledge-templates"], queryFn: fetchKnowledgeTemplates });
  const reviewQueueQuery = useQuery({ queryKey: ["knowledge-review-queue"], queryFn: fetchKnowledgeReviewQueue });
  const qualityQuery = useQuery({ queryKey: ["knowledge-quality"], queryFn: fetchKnowledgeQuality });
  const gapsQuery = useQuery({ queryKey: ["knowledge-gaps"], queryFn: fetchKnowledgeGaps });
  const rolloutPoliciesQuery = useQuery({
    queryKey: ["knowledge-rollout-policies"],
    queryFn: fetchKnowledgeRolloutPolicies,
    enabled: canManage,
  });

  const items = itemsQuery.data ?? [];
  const filteredItems = useMemo(() => {
    const needle = search.trim().toLowerCase();
    if (!needle) {
      return items;
    }
    return items.filter((item) =>
      [item.title, item.slug, item.summary, item.item_type, item.visibility, item.status].some((value) =>
        String(value ?? "").toLowerCase().includes(needle),
      ),
    );
  }, [items, search]);
  const selectedItem = items.find((item) => item.item_id === selectedItemId) ?? filteredItems[0] ?? null;
  const versionsQuery = useQuery({
    queryKey: ["knowledge-item-versions", selectedItem?.item_id],
    queryFn: () => fetchKnowledgeItemVersions(selectedItem?.item_id ?? ""),
    enabled: Boolean(selectedItem?.item_id),
  });
  const versions = versionsQuery.data ?? [];
  const latestVersion = versions[0] ?? null;
  const selectedVersion = versions.find((version) => version.version_id === selectedVersionId) ?? latestVersion;

  useEffect(() => {
    if (!selectedItem?.item_id) {
      setSelectedVersionId("");
      return;
    }
    setSelectedVersionId(selectedItem.current_version_id ?? latestVersion?.version_id ?? "");
  }, [latestVersion?.version_id, selectedItem?.current_version_id, selectedItem?.item_id]);

  const saveSpaceMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeSpace({
        ...spaceDraft,
        owner_actor_id: emptyToNull(spaceDraft.owner_actor_id),
        default_reviewer_actor_id: emptyToNull(spaceDraft.default_reviewer_actor_id),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-spaces"] }),
  });
  const createItemMutation = useMutation({
    mutationFn: () =>
      createKnowledgeItem({
        space_code: itemDraft.space_code,
        slug: itemDraft.slug || itemDraft.title,
        item_type: itemDraft.item_type,
        title: itemDraft.title,
        summary: emptyToNull(itemDraft.summary),
        visibility: itemDraft.visibility,
        owner_actor_id: emptyToNull(itemDraft.owner_actor_id),
        reviewer_actor_id: emptyToNull(itemDraft.reviewer_actor_id),
        bindings:
          itemDraft.service_code || itemDraft.offering_code || itemDraft.request_template_key
            ? [
                {
                  service_code: emptyToNull(itemDraft.service_code),
                  offering_code: emptyToNull(itemDraft.offering_code),
                  request_template_key: emptyToNull(itemDraft.request_template_key),
                },
              ]
            : [],
      }),
    onSuccess: (result) => {
      setSelectedItemId(result.item.item_id);
      setVersionDraft((current) => ({ ...current, title: result.item.title, summary: result.item.summary ?? "" }));
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
    },
  });
  const createVersionMutation = useMutation({
    mutationFn: () => createKnowledgeVersion(selectedItem?.item_id ?? "", versionDraft),
    onSuccess: (result) => {
      setSelectedVersionId(result.version.version_id);
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-versions", selectedItem?.item_id] });
    },
  });
  const publishMutation = useMutation({
    mutationFn: () =>
      publishKnowledgeItem(selectedItem?.item_id ?? "", selectedVersionId, {
        acknowledge_stale_passport: acknowledgeStalePassport,
        review_note: emptyToNull(reviewNote),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-versions", selectedItem?.item_id] });
    },
  });
  const contentPackMutation = useMutation({
    mutationFn: (options: { dryRun: boolean }) => {
      const pack = JSON.parse(contentPackText) as Record<string, unknown>;
      return applyKnowledgeContentPack({ pack, dry_run: options.dryRun, force: contentPackForce });
    },
    onSuccess: (result) => {
      setContentPackResult(JSON.stringify(result.result, null, 2));
      queryClient.invalidateQueries({ queryKey: ["knowledge-content-packs"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-spaces"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-review-queue"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
    },
    onError: (error) => setContentPackResult(error instanceof Error ? error.message : "content pack failed"),
  });
  const retirePackMutation = useMutation({
    mutationFn: retireKnowledgeContentPack,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-content-packs"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-review-queue"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
    },
  });
  const reviewActionMutation = useMutation<unknown, Error, { itemId: string; taskId?: string; action: string }>({
    mutationFn: (payload: { itemId: string; taskId?: string; action: string }) => {
      if (payload.taskId && ["assign", "start", "complete", "dismiss"].includes(payload.action)) {
        return submitKnowledgeReviewTaskAction(payload.taskId, {
          action: payload.action as "assign" | "start" | "complete" | "dismiss",
          note: emptyToNull(reviewNote),
        });
      }
      return submitKnowledgeReviewAction(payload.itemId, { action: payload.action, note: emptyToNull(reviewNote) });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-review-queue"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-quality"] });
    },
  });
  const gapActionMutation = useMutation({
    mutationFn: (payload: { findingId: string; action: "dismiss" | "create-draft" }) =>
      submitKnowledgeGapAction(payload.findingId, payload.action, payload.action === "create-draft" ? { item_type: "article" } : { reason: "Handled from operations dashboard" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["knowledge-gaps"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-review-queue"] });
      queryClient.invalidateQueries({ queryKey: ["knowledge-items"] });
    },
  });
  const gapRecomputeMutation = useMutation({
    mutationFn: recomputeKnowledgeGaps,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-gaps"] }),
  });
  const rolloutPolicyMutation = useMutation({
    mutationFn: () =>
      saveKnowledgeRolloutPolicy({
        ...rolloutDraft,
        service_code: emptyToNull(rolloutDraft.service_code),
        offering_code: emptyToNull(rolloutDraft.offering_code),
        request_template_key: emptyToNull(rolloutDraft.request_template_key),
        reason: emptyToNull(rolloutDraft.reason),
        rollout_percent: rolloutDraft.rollout_percent,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-rollout-policies"] }),
  });

  const metrics = metricsQuery.data;
  const deflectedCount = metrics?.deflection?.deflected_count ?? metrics?.deflection_events ?? 0;
  const helpfulCount = metrics?.helpfulness?.helpful_count ?? metrics?.helpful_events ?? 0;
  const notHelpfulCount = metrics?.helpfulness?.not_helpful_count ?? metrics?.not_helpful_events ?? 0;
  const ticketAfterViewCount = metrics?.deflection?.ticket_created_after_view_count ?? metrics?.ticket_created_after_view_events ?? 0;
  const reviewQueue = reviewQueueQuery.data?.items ?? [];
  const qualityItems = qualityQuery.data?.items ?? [];
  const gaps = gapsQuery.data?.gaps ?? [];
  const rolloutPolicies = rolloutPoliciesQuery.data ?? [];

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Platform"
        title="Платформа знаний"
        description="Пространства, универсальные knowledge items, версии, ACL, публикация и deflection-метрики."
      />

      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
        <Card>
          <CardHeader>
            <CardTitle>Items</CardTitle>
            <CardDescription>Всего объектов знаний</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{items.length}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Published</CardTitle>
            <CardDescription>Доступны по ACL</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{items.filter((item) => item.status === "published").length}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Deflection</CardTitle>
            <CardDescription>Помогло без тикета</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{deflectedCount}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Helpfulness</CardTitle>
            <CardDescription>Полезно / не полезно</CardDescription>
          </CardHeader>
          <CardContent className="text-lg font-semibold">
            {helpfulCount} / {notHelpfulCount}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Review</CardTitle>
            <CardDescription>Очередь курации</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{reviewQueueQuery.data?.count ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Quality</CardTitle>
            <CardDescription>Средний score</CardDescription>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{Math.round(qualityQuery.data?.average_quality_score ?? 0)}</CardContent>
        </Card>
      </div>
      {ticketAfterViewCount ? <p className="text-sm text-slate-500">Ticket after knowledge view: {ticketAfterViewCount}</p> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <div className="space-y-6">
          {canManage ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <PackageCheck className="h-5 w-5" />
                  Content packs
                </CardTitle>
                <CardDescription>Идемпотентная установка, dry-run, force overwrite и retire без SQL dump.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.8fr)]">
                  <div>
                    <label className="text-sm font-medium">
                      Pack JSON
                      <textarea className={textareaClass} value={contentPackText} onChange={(event) => setContentPackText(event.target.value)} />
                    </label>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={contentPackForce} onChange={(event) => setContentPackForce(event.target.checked)} />
                        Force overwrite admin edits
                      </label>
                      <Button variant="outline" onClick={() => contentPackMutation.mutate({ dryRun: true })} disabled={contentPackMutation.isPending}>
                        Dry-run
                      </Button>
                      <Button onClick={() => contentPackMutation.mutate({ dryRun: false })} disabled={contentPackMutation.isPending}>
                        Install / update
                      </Button>
                    </div>
                  </div>
                  <div>
                    <div className="rounded-md border border-slate-200">
                      <div className="border-b border-slate-100 px-3 py-2 text-xs font-semibold uppercase text-slate-500">Installed packs</div>
                      <div className="max-h-60 overflow-auto">
                        {(contentPacksQuery.data ?? []).map((pack) => (
                          <div key={pack.pack_id} className="border-b border-slate-100 px-3 py-2 text-sm last:border-b-0">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="font-medium">{pack.title}</p>
                                <p className="text-xs text-slate-500">
                                  {pack.code} v{pack.version} · {formatDate(pack.installed_at)}
                                </p>
                              </div>
                              <Badge tone={tone(pack.status)}>{pack.status}</Badge>
                            </div>
                            <Button
                              className="mt-2"
                              variant="outline"
                              size="sm"
                              onClick={() => retirePackMutation.mutate(pack.code)}
                              disabled={retirePackMutation.isPending}
                            >
                              Retire
                            </Button>
                          </div>
                        ))}
                        {!contentPacksQuery.data?.length ? <p className="p-3 text-sm text-slate-500">Content packs ещё не установлены.</p> : null}
                      </div>
                    </div>
                    {contentPackResult ? <pre className="mt-3 max-h-48 overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-100">{contentPackResult}</pre> : null}
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ClipboardCheck className="h-5 w-5" />
                Review / curation queue
              </CardTitle>
              <CardDescription>Draft, in-review, needs-review и overdue материалы из реальных knowledge items.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="overflow-hidden rounded-md border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Item</th>
                      <th className="px-3 py-2">Reason</th>
                      <th className="px-3 py-2">Visibility</th>
                      <th className="px-3 py-2">Due</th>
                      <th className="px-3 py-2">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reviewQueue.slice(0, 8).map((item) => (
                      <tr key={item.item_id} className="border-t border-slate-100">
                        <td className="px-3 py-2">
                          <button className="text-left font-medium text-slate-900 hover:text-blue-700" onClick={() => setSelectedItemId(item.item_id)}>
                            {item.title}
                          </button>
                          <p className="text-xs text-slate-500">{item.slug}</p>
                        </td>
                        <td className="px-3 py-2"><Badge tone={tone(item.reason)}>{item.reason}</Badge></td>
                        <td className="px-3 py-2">{item.visibility}</td>
                        <td className="px-3 py-2">{formatDate(item.review_due_at)}</td>
                        <td className="px-3 py-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => reviewActionMutation.mutate({ itemId: item.item_id, taskId: item.task_id, action: reviewActionDraft })}
                            disabled={!canOperate || reviewActionMutation.isPending}
                          >
                            Apply
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!reviewQueue.length ? <p className="p-4 text-sm text-slate-500">Очередь review пуста.</p> : null}
              </div>
              <div className="grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
                <label className="text-sm font-medium">
                  Review action
                  <select className={fieldClass} value={reviewActionDraft} onChange={(event) => setReviewActionDraft(event.target.value)}>
                    <option value="assign">assign</option>
                    <option value="start">start</option>
                    <option value="complete">complete</option>
                    <option value="dismiss">dismiss</option>
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Note
                  <input className={fieldClass} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
                </label>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Gauge className="h-5 w-5" />
                Knowledge quality score
              </CardTitle>
              <CardDescription>Score учитывает публикацию, тело версии, reviewer, bindings, review freshness, feedback и requester-safe lint.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-hidden rounded-md border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Item</th>
                      <th className="px-3 py-2">Score</th>
                      <th className="px-3 py-2">Issues</th>
                    </tr>
                  </thead>
                  <tbody>
                    {qualityItems.slice(0, 10).map((item) => (
                      <tr key={item.item_id} className="border-t border-slate-100">
                        <td className="px-3 py-2">
                          <button className="text-left font-medium hover:text-blue-700" onClick={() => setSelectedItemId(item.item_id)}>
                            {item.title}
                          </button>
                          <p className="text-xs text-slate-500">{item.visibility} · {item.status}</p>
                        </td>
                        <td className="px-3 py-2"><Badge tone={qualityTone(item.quality_score)}>{item.quality_score}</Badge></td>
                        <td className="px-3 py-2 text-xs text-slate-600">{item.issues?.join(", ") || "ok"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!qualityItems.length ? <p className="p-4 text-sm text-slate-500">Нет quality данных.</p> : null}
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Knowledge gaps
              </CardTitle>
              <CardDescription>Service Catalog offerings без requester-safe знаний, с ticket/feedback сигналами.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {canOperate ? (
                <Button variant="outline" size="sm" onClick={() => gapRecomputeMutation.mutate()} disabled={gapRecomputeMutation.isPending}>
                  Recompute gaps
                </Button>
              ) : null}
              {gaps.slice(0, 8).map((gap) => (
                <div key={gap.finding_id ?? `${gap.service_code}:${gap.offering_code}:${gap.gap_type}`} className="rounded-md border border-slate-200 p-3 text-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium">{gap.offering_title || gap.offering_code}</p>
                      <p className="text-xs text-slate-500">{gap.service_code} / {gap.offering_code}</p>
                    </div>
                    <Badge tone={gap.severity === "high" ? "danger" : "warning"}>{gap.severity}</Badge>
                  </div>
                  <p className="mt-2 text-xs text-slate-600">
                    Tickets: {gap.ticket_count}; after view: {gap.ticket_created_after_view_count}; not helpful: {gap.not_helpful_count}
                  </p>
                  {canOperate && gap.finding_id ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" onClick={() => gapActionMutation.mutate({ findingId: gap.finding_id!, action: "create-draft" })} disabled={gapActionMutation.isPending}>
                        Create draft
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => gapActionMutation.mutate({ findingId: gap.finding_id!, action: "dismiss" })} disabled={gapActionMutation.isPending}>
                        Dismiss
                      </Button>
                    </div>
                  ) : null}
                </div>
              ))}
              {!gaps.length ? <p className="text-sm text-slate-500">Гэпы по опубликованному Service Catalog не найдены.</p> : null}
            </CardContent>
          </Card>

          {canManage ? (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <SlidersHorizontal className="h-5 w-5" />
                  Deflection rollout
                </CardTitle>
                <CardDescription>Управляет requester/agent self-service deflection, support workspace не блокируется.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3">
                  <label className="text-sm font-medium">
                    Surface
                    <select className={fieldClass} value={rolloutDraft.surface} onChange={(event) => setRolloutDraft({ ...rolloutDraft, surface: event.target.value })}>
                      <option value="requester_portal">requester_portal</option>
                      <option value="ticket_create">ticket_create</option>
                      <option value="agent_gui">agent_gui</option>
                      <option value="api">api</option>
                    </select>
                  </label>
                  <label className="text-sm font-medium">
                    Service
                    <input className={fieldClass} value={rolloutDraft.service_code} onChange={(event) => setRolloutDraft({ ...rolloutDraft, service_code: event.target.value })} />
                  </label>
                  <label className="text-sm font-medium">
                    Offering
                    <input className={fieldClass} value={rolloutDraft.offering_code} onChange={(event) => setRolloutDraft({ ...rolloutDraft, offering_code: event.target.value })} />
                  </label>
                  <label className="text-sm font-medium">
                    Request template
                    <input className={fieldClass} value={rolloutDraft.request_template_key} onChange={(event) => setRolloutDraft({ ...rolloutDraft, request_template_key: event.target.value })} />
                  </label>
                  <label className="text-sm font-medium">
                    Rollout percent
                    <input
                      className={fieldClass}
                      type="number"
                      min={0}
                      max={100}
                      value={rolloutDraft.rollout_percent}
                      onChange={(event) => setRolloutDraft({ ...rolloutDraft, rollout_percent: Number(event.target.value) })}
                    />
                  </label>
                  <label className="text-sm font-medium">
                    Reason
                    <input className={fieldClass} value={rolloutDraft.reason} onChange={(event) => setRolloutDraft({ ...rolloutDraft, reason: event.target.value })} />
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={rolloutDraft.enabled} onChange={(event) => setRolloutDraft({ ...rolloutDraft, enabled: event.target.checked })} />
                    Enabled
                  </label>
                  <Button onClick={() => rolloutPolicyMutation.mutate()} disabled={rolloutPolicyMutation.isPending}>
                    Save policy
                  </Button>
                </div>
                <div className="space-y-2">
                  {rolloutPolicies.slice(0, 6).map((policy) => (
                    <div key={policy.policy_id} className="rounded-md border border-slate-200 p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{policy.surface}</span>
                        <Badge tone={policy.enabled ? "success" : "danger"}>{policy.enabled ? "enabled" : "disabled"}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        {policy.service_code || "*"} / {policy.offering_code || "*"} · {policy.rollout_percent}% · {policy.reason || "no reason"}
                      </p>
                    </div>
                  ))}
                  {!rolloutPolicies.length ? <p className="text-sm text-slate-500">Rollout policies не заданы.</p> : null}
                </div>
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Templates
              </CardTitle>
              <CardDescription>Шаблоны body-структуры для разных типов знаний.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {(templatesQuery.data ?? []).map((template) => (
                <div key={template.type} className="rounded-md border border-slate-200 p-3 text-sm">
                  <p className="font-medium">{template.title}</p>
                  <p className="text-xs text-slate-500">{template.type}</p>
                  <p className="mt-1 text-xs text-slate-600">{template.sections.join(" · ")}</p>
                </div>
              ))}
              {!templatesQuery.data?.length ? <p className="text-sm text-slate-500">Шаблоны не загрузились.</p> : null}
            </CardContent>
          </Card>
        </aside>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-6">
          {canManage ? (
          <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Пространства
              </CardTitle>
              <CardDescription>ACL и lifecycle задаются на уровне space, item и версии.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <label className="text-sm font-medium">
                  Code
                  <input className={fieldClass} value={spaceDraft.code} onChange={(event) => setSpaceDraft({ ...spaceDraft, code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Title
                  <input className={fieldClass} value={spaceDraft.title} onChange={(event) => setSpaceDraft({ ...spaceDraft, title: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Visibility
                  <select className={fieldClass} value={spaceDraft.visibility} onChange={(event) => setSpaceDraft({ ...spaceDraft, visibility: event.target.value })}>
                    <option value="requester">requester</option>
                    <option value="agent_requester_safe">agent_requester_safe</option>
                    <option value="support_internal">support_internal</option>
                    <option value="admin_internal">admin_internal</option>
                    <option value="security_restricted">security_restricted</option>
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Owner
                  <input className={fieldClass} value={spaceDraft.owner_actor_id} onChange={(event) => setSpaceDraft({ ...spaceDraft, owner_actor_id: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Reviewer
                  <input className={fieldClass} value={spaceDraft.default_reviewer_actor_id} onChange={(event) => setSpaceDraft({ ...spaceDraft, default_reviewer_actor_id: event.target.value })} />
                </label>
                <div className="flex items-end">
                  <Button onClick={() => saveSpaceMutation.mutate()} disabled={saveSpaceMutation.isPending}>
                    Сохранить space
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {(spacesQuery.data ?? []).map((space) => (
                  <Badge key={space.space_id} tone={tone(space.lifecycle_status)}>
                    {space.code} · {space.visibility}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BookOpenCheck className="h-5 w-5" />
                Knowledge items
              </CardTitle>
              <CardDescription>Article - только один из типов. Черновик публикуется только после версии и reviewer.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-3">
                <label className="text-sm font-medium">
                  Space
                  <input className={fieldClass} value={itemDraft.space_code} onChange={(event) => setItemDraft({ ...itemDraft, space_code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Type
                  <select className={fieldClass} value={itemDraft.item_type} onChange={(event) => setItemDraft({ ...itemDraft, item_type: event.target.value })}>
                    {["article", "faq", "runbook", "policy", "document", "known_error", "workaround", "troubleshooting_tree", "glossary_term", "service_description", "external_source", "resolution_draft"].map((type) => (
                      <option key={type} value={type}>
                        {itemTypeLabel(type)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-medium">
                  Visibility
                  <select className={fieldClass} value={itemDraft.visibility} onChange={(event) => setItemDraft({ ...itemDraft, visibility: event.target.value })}>
                    <option value="requester">requester</option>
                    <option value="agent_requester_safe">agent_requester_safe</option>
                    <option value="support_internal">support_internal</option>
                    <option value="admin_internal">admin_internal</option>
                    <option value="security_restricted">security_restricted</option>
                  </select>
                </label>
                <label className="text-sm font-medium md:col-span-2">
                  Title
                  <input className={fieldClass} value={itemDraft.title} onChange={(event) => setItemDraft({ ...itemDraft, title: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Slug
                  <input className={fieldClass} value={itemDraft.slug} onChange={(event) => setItemDraft({ ...itemDraft, slug: event.target.value })} />
                </label>
                <label className="text-sm font-medium md:col-span-3">
                  Summary
                  <input className={fieldClass} value={itemDraft.summary} onChange={(event) => setItemDraft({ ...itemDraft, summary: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Owner
                  <input className={fieldClass} value={itemDraft.owner_actor_id} onChange={(event) => setItemDraft({ ...itemDraft, owner_actor_id: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Reviewer
                  <input className={fieldClass} value={itemDraft.reviewer_actor_id} onChange={(event) => setItemDraft({ ...itemDraft, reviewer_actor_id: event.target.value })} />
                </label>
                <div className="flex items-end">
                  <Button onClick={() => createItemMutation.mutate()} disabled={!itemDraft.title || createItemMutation.isPending}>
                    Создать draft
                  </Button>
                </div>
                <label className="text-sm font-medium">
                  Service binding
                  <input className={fieldClass} value={itemDraft.service_code} onChange={(event) => setItemDraft({ ...itemDraft, service_code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Offering binding
                  <input className={fieldClass} value={itemDraft.offering_code} onChange={(event) => setItemDraft({ ...itemDraft, offering_code: event.target.value })} />
                </label>
                <label className="text-sm font-medium">
                  Request template
                  <input className={fieldClass} value={itemDraft.request_template_key} onChange={(event) => setItemDraft({ ...itemDraft, request_template_key: event.target.value })} />
                </label>
              </div>
            </CardContent>
          </Card>
          </>
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Search className="h-5 w-5" />
                Реестр знаний
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <input className={fieldClass} placeholder="Поиск по title, slug, type, visibility" value={search} onChange={(event) => setSearch(event.target.value)} />
              <div className="overflow-hidden rounded-md border border-slate-200">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Title</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Visibility</th>
                      <th className="px-3 py-2">Version</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredItems.map((item) => (
                      <tr key={item.item_id} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50" onClick={() => setSelectedItemId(item.item_id)}>
                        <td className="px-3 py-2 font-medium">{item.title}</td>
                        <td className="px-3 py-2">{itemTypeLabel(item.item_type)}</td>
                        <td className="px-3 py-2">
                          <Badge tone={tone(item.status)}>{item.status}</Badge>
                        </td>
                        <td className="px-3 py-2">{item.visibility}</td>
                        <td className="px-3 py-2">{item.current_version?.version_number ?? "draft"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!filteredItems.length ? <p className="p-4 text-sm text-slate-500">Нет объектов знаний по текущему фильтру.</p> : null}
              </div>
            </CardContent>
          </Card>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Версия и публикация</CardTitle>
              <CardDescription>{selectedItem ? selectedItem.title : "Выберите item из реестра"}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {selectedItem ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={tone(selectedItem.status)}>{selectedItem.status}</Badge>
                    <Badge tone={tone(selectedItem.visibility)}>{selectedItem.visibility}</Badge>
                    <Badge tone="neutral">{itemTypeLabel(selectedItem.item_type)}</Badge>
                  </div>
                  <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                    Current published: {selectedItem.current_version?.version_number ?? "none"}. Latest version: {latestVersion?.version_number ?? "none"}. Selected version: {selectedVersion?.version_number ?? "none"}.
                  </div>
                  {canManage ? (
                    <label className="text-sm font-medium">
                      Selected version
                      <select className={fieldClass} value={selectedVersionId} onChange={(event) => setSelectedVersionId(event.target.value)}>
                        <option value="">Select a version</option>
                        {versions.map((version) => (
                          <option key={version.version_id} value={version.version_id}>
                            v{version.version_number} {version.published_at ? "(published)" : "(draft)"} {version.version_id.slice(0, 8)}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : null}
                  <label className="text-sm font-medium">
                    Version title
                    <input className={fieldClass} value={versionDraft.title || selectedItem.title} onChange={(event) => setVersionDraft({ ...versionDraft, title: event.target.value })} />
                  </label>
                  <label className="text-sm font-medium">
                    Body
                    <textarea className={`${fieldClass} min-h-48`} value={versionDraft.body} onChange={(event) => setVersionDraft({ ...versionDraft, body: event.target.value })} />
                  </label>
                  <label className="text-sm font-medium">
                    Review note
                    <input className={fieldClass} value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} />
                  </label>
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={acknowledgeStalePassport} onChange={(event) => setAcknowledgeStalePassport(event.target.checked)} />
                    Acknowledge stale passport source
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => createVersionMutation.mutate()} disabled={!canManage || !versionDraft.body || createVersionMutation.isPending}>
                      Создать версию
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => publishMutation.mutate()}
                      disabled={!canManage || !selectedVersionId || publishMutation.isPending}
                    >
                      Опубликовать
                    </Button>
                  </div>
                  <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-600">
                    Текущая версия: {selectedItem.current_version?.version_number ?? "нет"}. Публикация требует reviewer в item.
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Создайте или выберите knowledge item.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Graph и bindings
              </CardTitle>
              <CardDescription>Связи создаются backend-сервисом при binding, feedback и draft-from-passport.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Для выбранного item graph foundation хранит service/offering edges, known errors, workarounds и source relations. В P2 UI показывает управляющий контур и безопасные binding поля; raw graph metadata не выводится.
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <UploadCloud className="h-5 w-5" />
                Ingestion
              </CardTitle>
              <CardDescription>Markdown/text ingestion создаёт draft, version и chunks без auto-publish.</CardDescription>
            </CardHeader>
            <CardContent className="text-sm text-slate-600">
              Для массовой загрузки используется backend ingestion service. По умолчанию imported sources остаются internal draft и требуют review.
            </CardContent>
          </Card>
        </aside>
      </div>

      {spacesQuery.isError || itemsQuery.isError || metricsQuery.isError ? (
        <Card>
          <CardContent className="p-4 text-sm text-red-700">Часть данных knowledge platform не загрузилась. Проверьте RBAC и backend API.</CardContent>
        </Card>
      ) : null}
    </section>
  );
}
