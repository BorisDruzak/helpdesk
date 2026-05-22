import { ArrowUpRight, CheckCircle2, RefreshCcw, Search, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { StatTile } from "../../components/ui/stat-tile";
import {
  approveAdminRegistrationClaim,
  fetchAdminRegistry,
  rejectAdminRegistrationClaim,
  type AdminRegistryPayload,
  type AdminRegistrationClaim,
} from "../../features/admin/api";
import { cn } from "../../shared/ui/cn";

type TabKey = "assets" | "registrations" | "people" | "locations" | "quality" | "services";

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: "assets", label: "Объекты" },
  { key: "registrations", label: "Регистрация" },
  { key: "people", label: "Люди" },
  { key: "locations", label: "Здания" },
  { key: "quality", label: "Качество" },
  { key: "services", label: "Сервисы" },
];

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "Нет данных";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function statusTone(value: string | null | undefined): "brand" | "info" | "neutral" | "success" | "warning" {
  const normalized = String(value ?? "").trim().toLowerCase();
  if (normalized === "active" || normalized === "verified" || normalized === "admin_confirmed" || normalized === "approved") {
    return "success";
  }
  if (normalized === "pending" || normalized === "self_reported" || normalized === "pending_user_confirmation" || normalized === "user_confirmed" || normalized === "pending_admin_review") {
    return "warning";
  }
  if (normalized === "unverified" || normalized === "conflict" || normalized === "rejected" || normalized === "stale") {
    return "info";
  }
  if (normalized === "agent") {
    return "brand";
  }
  return "neutral";
}

function filterText(value: AdminRegistryPayload, query: string) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return value;
  }
  const includes = (...parts: Array<string | null | undefined>) =>
    parts.filter(Boolean).join(" ").toLowerCase().includes(normalized);
  return {
    ...value,
    assets: value.assets.filter((asset) =>
      includes(asset.name, asset.hostname, asset.device_id, asset.owner_name, asset.department_name, asset.location_name, asset.service_name)
    ),
    people: value.people.filter((person) =>
      includes(person.display_name, person.full_name, person.phone, person.email, person.department_name, person.location_name)
    ),
    locations: value.locations.filter((location) =>
      includes(location.display_name, location.building, location.floor, location.room)
    ),
    departments: value.departments.filter((department) => includes(department.name, department.code)),
    services: value.services.filter((service) => includes(service.name, service.code, service.support_queue)),
    vendors: value.vendors.filter((vendor) => includes(vendor.name, vendor.code, vendor.contact_name, vendor.phone, vendor.email)),
  };
}

function EmptyState({ label }: { label: string }) {
  return <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">{label}</p>;
}

function profileValue(claim: AdminRegistrationClaim, key: string): string | null {
  const value = claim.profile_snapshot?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function claimDisplayName(claim: AdminRegistrationClaim): string {
  return claim.person_name ?? profileValue(claim, "display_name") ?? profileValue(claim, "full_name") ?? profileValue(claim, "login") ?? "Пользователь не определен";
}

export function AdminRegistryPage() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<TabKey>("assets");
  const [actionClaimId, setActionClaimId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const registryQuery = useQuery({
    queryKey: ["admin-registry"],
    queryFn: fetchAdminRegistry,
    retry: false,
    refetchInterval: 15_000,
  });

  const registry = registryQuery.data;
  const visibleRegistry = useMemo(
    () => (registry ? filterText(registry, query) : null),
    [query, registry]
  );
  const visibleClaims = useMemo(() => {
    const claims = registry?.registration_claims ?? [];
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return claims;
    }
    return claims.filter((claim) =>
      [
        claim.device_id,
        claim.status,
        claim.relationship_type,
        claim.conflict_reason,
        claimDisplayName(claim),
        profileValue(claim, "department"),
        profileValue(claim, "building"),
        profileValue(claim, "room"),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(normalized)
    );
  }, [query, registry]);
  const firstAssetWithDevice = visibleRegistry?.assets.find((asset) => asset.device_id) ?? null;

  const runClaimAction = async (claim: AdminRegistrationClaim, action: "approve" | "replace" | "reject" | "override") => {
    setActionError(null);
    setActionClaimId(claim.claim_id);
    try {
      if (action === "reject") {
        const reason = window.prompt("Причина отклонения заявки", "Данные не подтверждены") ?? "";
        if (!reason.trim()) {
          return;
        }
        await rejectAdminRegistrationClaim(claim.claim_id, reason.trim());
      } else if (action === "override") {
        const reason = window.prompt("Причина админского подтверждения без пользователя", "Проверено администратором") ?? "";
        if (!reason.trim()) {
          return;
        }
        await approveAdminRegistrationClaim(claim.claim_id, false, true, reason.trim());
      } else {
        await approveAdminRegistrationClaim(claim.claim_id, action === "replace");
      }
      await registryQuery.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Не удалось выполнить действие");
    } finally {
      setActionClaimId(null);
    }
  };

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button
              leadingIcon={<RefreshCcw className="h-4 w-4" />}
              onClick={() => void registryQuery.refetch()}
              size="sm"
              variant="outline"
            >
              Обновить
            </Button>
            <Button
              disabled={!firstAssetWithDevice}
              leadingIcon={<ArrowUpRight className="h-4 w-4" />}
              onClick={() => {
                if (firstAssetWithDevice?.device_id) {
                  navigate(`/app/admin/device?device=${encodeURIComponent(firstAssetWithDevice.device_id)}`);
                }
              }}
              size="sm"
            >
              Карточка ПК
            </Button>
          </>
        }
        description="Люди, здания, кабинеты, ПК, принтеры, сервисы, подрядчики и очереди поддержки в одном рабочем слое."
        eyebrow="Admin workspace"
        title="Реестры"
      />

      <div className="grid gap-4 xl:grid-cols-4">
        <StatTile helper="ПК, принтеры и связанные активы" label="Объекты" value={String(registry?.summary.assets ?? 0)} />
        <StatTile helper="Профили агента, AD и ручной ввод" label="Люди" value={String(registry?.summary.people ?? 0)} />
        <StatTile helper="Здания, этажи и кабинеты" label="Локации" value={String(registry?.summary.locations ?? 0)} />
        <StatTile helper="Проверки и автосвязи" label="Сигналы" value={String((registry?.summary.data_quality_issues ?? 0) + (registry?.summary.suggestions ?? 0))} />
      </div>

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>Операционный реестр</CardTitle>
              <CardDescription>Связи тикетов с человеком, местом, устройством и системой.</CardDescription>
            </div>
            <div className="flex min-w-[280px] items-center gap-2">
              <Search className="h-4 w-4 text-slate-400" />
              <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Поиск по реестрам" value={query} />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {tabs.map((item) => (
              <button
                className={cn(
                  "rounded-pill px-3 py-2 text-sm font-semibold transition-colors",
                  tab === item.key ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600 hover:bg-brand-50 hover:text-brand-800"
                )}
                key={item.key}
                onClick={() => setTab(item.key)}
                type="button"
              >
                {item.label}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {registryQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем реестры...</p> : null}
          {registryQuery.isError ? (
            <p className="text-sm text-rose-600">
              {registryQuery.error instanceof Error ? registryQuery.error.message : "Не удалось загрузить реестры."}
            </p>
          ) : null}

          {tab === "assets" ? (
            <div className="overflow-x-auto rounded-lg border border-border">
              <div className="grid min-w-[720px] grid-cols-[minmax(180px,1.4fr)_minmax(150px,1fr)_minmax(160px,1fr)_120px_120px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
                <span>Объект</span>
                <span>Владелец</span>
                <span>Место</span>
                <span>Тикеты</span>
                <span>Статус</span>
              </div>
              {(visibleRegistry?.assets ?? []).length ? (
                visibleRegistry?.assets.map((asset) => (
                  <div className="grid min-w-[720px] grid-cols-[minmax(180px,1.4fr)_minmax(150px,1fr)_minmax(160px,1fr)_120px_120px] gap-3 border-t border-border px-4 py-3 text-sm" key={asset.id}>
                    <div>
                      <p className="font-semibold text-slate-950">{asset.name ?? asset.hostname ?? asset.device_id ?? "Объект"}</p>
                      <p className="mt-1 text-xs text-slate-500">{asset.asset_type} · {asset.hostname ?? "hostname нет"}</p>
                    </div>
                    <div className="space-y-1">
                      <p className="text-slate-700">{asset.active_person_name ?? asset.owner_name ?? "Не зарегистрирован"}</p>
                      <Badge tone={statusTone(asset.registration_status)}>{asset.registration_status ?? "unregistered"}</Badge>
                    </div>
                    <span className="text-slate-700">{asset.location_name ?? "Без кабинета"}</span>
                    <span className="text-slate-700">{asset.ticket_count}</span>
                    <Badge tone={statusTone(asset.status)}>{asset.status}</Badge>
                  </div>
                ))
              ) : (
                <div className="border-t border-border p-4">
                  <EmptyState label="Объекты пока не найдены." />
                </div>
              )}
            </div>
          ) : null}

          {tab === "registrations" ? (
            <div className="space-y-3">
              {actionError ? <p className="text-sm text-rose-600">{actionError}</p> : null}
              <div className="grid gap-3 md:grid-cols-5">
                <StatTile helper="Ожидают пользователя или администратора" label="Ожидают" value={String(registry?.summary.registrations_pending ?? 0)} />
                <StatTile helper="Требуют ручного решения" label="Конфликты" value={String(registry?.summary.registrations_conflicts ?? 0)} />
                <StatTile helper="Активные подтвержденные связи" label="Привязки" value={String(registry?.summary.active_bindings ?? 0)} />
                <StatTile helper="ПК без подтвержденного пользователя" label="Без регистрации" value={String(registry?.summary.unregistered_devices ?? 0)} />
                <StatTile helper="Истекшие или давно не виденные связи" label="Устаревшие" value={String(registry?.summary.stale_bindings ?? 0)} />
              </div>
              <div className="overflow-x-auto rounded-lg border border-border">
                <div className="grid min-w-[1040px] grid-cols-[minmax(170px,1fr)_180px_minmax(170px,1fr)_150px_150px_130px_110px_260px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
                  <span>ПК</span>
                  <span>Device ID</span>
                  <span>Заявленный пользователь</span>
                  <span>Presence</span>
                  <span>Локация</span>
                  <span>Статус</span>
                  <span>Confidence</span>
                  <span>Действия</span>
                </div>
                {visibleClaims.length ? visibleClaims.map((claim) => (
                  <div
                    className={cn(
                      "grid min-w-[1040px] grid-cols-[minmax(170px,1fr)_180px_minmax(170px,1fr)_150px_150px_130px_110px_260px] gap-3 border-t border-border px-4 py-3 text-sm",
                      claim.status === "conflict" ? "bg-amber-50" : "bg-white"
                    )}
                    key={claim.claim_id}
                  >
                    <div>
                      <p className="font-semibold text-slate-950">{profileValue(claim, "hostname") ?? "ПК"}</p>
                      <p className="mt-1 text-xs text-slate-500">{formatDateTime(claim.submitted_at)}</p>
                    </div>
                    <button
                      className="truncate text-left text-brand-700 hover:text-brand-900"
                      onClick={() => navigate(`/app/admin/device?device=${encodeURIComponent(claim.device_id)}`)}
                      type="button"
                    >
                      {claim.device_id}
                    </button>
                    <div>
                      <p className="font-medium text-slate-800">{claimDisplayName(claim)}</p>
                      <p className="mt-1 text-xs text-slate-500">{claim.relationship_type}</p>
                    </div>
                    <span className="text-slate-700">{profileValue(claim, "current_user") ?? profileValue(claim, "login") ?? "Нет данных"}</span>
                    <span className="text-slate-700">{[profileValue(claim, "building"), profileValue(claim, "floor"), profileValue(claim, "room")].filter(Boolean).join(" · ") || "Не указана"}</span>
                    <div className="space-y-1">
                      <Badge tone={statusTone(claim.status)}>{claim.status}</Badge>
                      {claim.conflict_reason ? <p className="text-xs text-amber-700">{claim.conflict_reason}</p> : null}
                    </div>
                    <span className="text-slate-700">{claim.confidence == null ? "-" : `${Math.round(claim.confidence * 100)}%`}</span>
                    <div className="flex flex-wrap gap-2">
                      {claim.status === "pending_user_confirmation" || claim.status === "self_reported" ? (
                        <Button
                          disabled={actionClaimId === claim.claim_id}
                          onClick={() => void runClaimAction(claim, "override")}
                          size="sm"
                          variant="outline"
                        >
                          Админское подтверждение
                        </Button>
                      ) : (
                        <Button
                          disabled={actionClaimId === claim.claim_id}
                          onClick={() => void runClaimAction(claim, "approve")}
                          size="sm"
                          variant="outline"
                        >
                          Подтвердить
                        </Button>
                      )}
                      {claim.status === "conflict" ? (
                        <Button
                          disabled={actionClaimId === claim.claim_id}
                          onClick={() => void runClaimAction(claim, "replace")}
                          size="sm"
                          variant="outline"
                        >
                          С заменой
                        </Button>
                      ) : null}
                      <Button
                        disabled={actionClaimId === claim.claim_id}
                        onClick={() => void runClaimAction(claim, "reject")}
                        size="sm"
                        variant="ghost"
                      >
                        Отклонить
                      </Button>
                    </div>
                  </div>
                )) : (
                  <div className="border-t border-border p-4">
                    <EmptyState label="Заявки регистрации пока не найдены." />
                  </div>
                )}
              </div>
            </div>
          ) : null}

          {tab === "people" ? (
            <div className="grid gap-3 lg:grid-cols-2">
              {(visibleRegistry?.people ?? []).length ? visibleRegistry?.people.map((person) => (
                <div className="rounded-lg border border-border bg-white px-4 py-4" key={person.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-950">{person.full_name ?? person.display_name}</p>
                      <p className="mt-1 text-sm text-slate-500">{person.department_name ?? "Подразделение не указано"}</p>
                    </div>
                    <Badge tone={statusTone(person.status)}>{person.source}</Badge>
                  </div>
                  <p className="mt-3 text-sm text-slate-600">{person.location_name ?? "Без кабинета"} · {person.phone ?? "телефон не указан"}</p>
                </div>
              )) : <EmptyState label="Люди пока не найдены." />}
            </div>
          ) : null}

          {tab === "locations" ? (
            <div className="grid gap-3 lg:grid-cols-3">
              {(visibleRegistry?.locations ?? []).length ? visibleRegistry?.locations.map((location) => (
                <div className="rounded-lg border border-border bg-white px-4 py-4" key={location.id}>
                  <p className="font-semibold text-slate-950">{location.display_name}</p>
                  <p className="mt-2 text-sm text-slate-500">Здание {location.building ?? "-"} · кабинет {location.room ?? "-"}</p>
                  <div className="mt-4 flex items-center justify-between gap-3">
                    <Badge tone={statusTone(location.status)}>{location.status}</Badge>
                    <span className="text-xs text-slate-400">{formatDateTime(location.updated_at)}</span>
                  </div>
                </div>
              )) : <EmptyState label="Здания и кабинеты пока не найдены." />}
            </div>
          ) : null}

          {tab === "quality" ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                  <CheckCircle2 className="h-4 w-4 text-amber-500" />
                  Data quality
                </div>
                {(registry?.data_quality ?? []).length ? registry?.data_quality.map((issue) => (
                  <div className="rounded-lg border border-border bg-white px-4 py-3" key={`${issue.kind}-${issue.object_id}`}>
                    <Badge tone={issue.severity}>{issue.object_type}</Badge>
                    <p className="mt-3 font-semibold text-slate-950">{issue.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{issue.description}</p>
                  </div>
                )) : <EmptyState label="Критичных пробелов нет." />}
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
                  <Sparkles className="h-4 w-4 text-brand-600" />
                  Автоподсказки
                </div>
                {(registry?.suggestions ?? []).length ? registry?.suggestions.map((suggestion) => (
                  <div className="rounded-lg border border-border bg-white px-4 py-3" key={`${suggestion.kind}-${suggestion.object_id}`}>
                    <Badge tone="info">{Math.round(suggestion.confidence * 100)}%</Badge>
                    <p className="mt-3 font-semibold text-slate-950">{suggestion.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{suggestion.description}</p>
                  </div>
                )) : <EmptyState label="Новых подсказок нет." />}
              </div>
            </div>
          ) : null}

          {tab === "services" ? (
            <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
              <div className="space-y-3">
                {(visibleRegistry?.services ?? []).length ? visibleRegistry?.services.map((service) => (
                  <div className="rounded-lg border border-border bg-white px-4 py-4" key={service.id}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-950">{service.name}</p>
                        <p className="mt-1 text-sm text-slate-500">{service.code ?? "code не указан"}</p>
                      </div>
                      <Badge tone={statusTone(service.status)}>{service.support_queue ?? "Очередь не задана"}</Badge>
                    </div>
                  </div>
                )) : <EmptyState label="Сервисы пока не заведены." />}
              </div>
              <div className="space-y-3">
                {(visibleRegistry?.vendors ?? []).length ? visibleRegistry?.vendors.map((vendor) => (
                  <div className="rounded-lg border border-border bg-white px-4 py-4" key={vendor.id}>
                    <p className="font-semibold text-slate-950">{vendor.name}</p>
                    <p className="mt-2 text-sm text-slate-500">{vendor.contact_name ?? "Контакт не указан"} · {vendor.phone ?? vendor.email ?? "канал не указан"}</p>
                  </div>
                )) : <EmptyState label="Подрядчики пока не заведены." />}
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}
