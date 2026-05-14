import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, GitBranch, Search, ShieldCheck, UploadCloud } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import {
  createKnowledgeItem,
  createKnowledgeVersion,
  fetchKnowledgeItems,
  fetchKnowledgeMetricsSummary,
  fetchKnowledgeSpaces,
  publishKnowledgeItem,
  saveKnowledgeSpace,
  type KnowledgeItem,
} from "./api";

const fieldClass = "mt-1 w-full rounded-md border border-slate-200 px-3 py-2 text-sm";

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

export function KnowledgeAdminPanel() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [selectedItemId, setSelectedItemId] = useState("");
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-items"] }),
  });
  const publishMutation = useMutation({
    mutationFn: () => publishKnowledgeItem(selectedItem?.item_id ?? "", selectedItem?.current_version_id ?? ""),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["knowledge-items"] }),
  });

  const metrics = metricsQuery.data;

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Platform"
        title="Платформа знаний"
        description="Пространства, универсальные knowledge items, версии, ACL, публикация и deflection-метрики."
      />

      <div className="grid gap-4 md:grid-cols-4">
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
          <CardContent className="text-3xl font-semibold">{metrics?.deflection_events ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Helpfulness</CardTitle>
            <CardDescription>Полезно / не полезно</CardDescription>
          </CardHeader>
          <CardContent className="text-lg font-semibold">
            {metrics?.helpful_events ?? 0} / {metrics?.not_helpful_events ?? 0}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="space-y-6">
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
                  <label className="text-sm font-medium">
                    Version title
                    <input className={fieldClass} value={versionDraft.title || selectedItem.title} onChange={(event) => setVersionDraft({ ...versionDraft, title: event.target.value })} />
                  </label>
                  <label className="text-sm font-medium">
                    Body
                    <textarea className={`${fieldClass} min-h-48`} value={versionDraft.body} onChange={(event) => setVersionDraft({ ...versionDraft, body: event.target.value })} />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={() => createVersionMutation.mutate()} disabled={!versionDraft.body || createVersionMutation.isPending}>
                      Создать версию
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => publishMutation.mutate()}
                      disabled={!selectedItem.current_version_id || publishMutation.isPending}
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
