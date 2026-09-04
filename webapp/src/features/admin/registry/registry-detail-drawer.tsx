import { X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { fetchAdminRegistryTimeline, type AdminRegistryPayload, type AdminRegistryTimelineItem } from "../api";
import { actorRoleLabel, formatDateTime, registrySourceLabel, registryStatusLabel, relationshipTypeLabel, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  registry: AdminRegistryPayload | null;
  selection: RegistrySelection;
  onClose: () => void;
};

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-slate-400">{label}</p>
      <p className="mt-1 break-words text-sm text-slate-800">{value ?? "Нет данных"}</p>
    </div>
  );
}

const EVENT_LABELS: Record<string, string> = {
  person_created: "Пользователь создан",
  person_updated: "Пользователь обновлен",
  identity_added: "Идентичность добавлена",
  identity_verified: "Идентичность подтверждена",
  identity_deleted: "Идентичность удалена",
  binding_created: "Привязка создана",
  admin_binding_created: "Привязка создана администратором",
  binding_activated: "Привязка активирована",
  binding_revoked: "Привязка отозвана",
  binding_transferred: "Привязка передана",
  shared_user_added: "Добавлен совместный пользователь",
  responsible_assigned: "Назначен ответственный",
  location_merged: "Локации объединены",
  department_merged: "Подразделения объединены",
  people_merged: "Пользователи объединены",
  person_merged: "Пользователи объединены",
  bulk_action_applied: "Массовая операция выполнена",
  policy_changed: "Политика изменена",
  registry_policy_updated: "Политика реестра изменена",
};

const RELATED_LABELS: Record<string, string> = {
  object_type: "Тип объекта",
  object_id: "ID объекта",
  device_id: "Устройство",
  person_id: "Пользователь",
  binding_id: "Привязка",
  claim_id: "Заявка",
  request_id: "Запрос",
  ticket_id: "Тикет",
  identity_id: "Идентичность",
  location_id: "Локация",
  department_id: "Подразделение",
};

function timelineTypeLabel(event: AdminRegistryTimelineItem) {
  const canonical = event.canonical_event_type ?? event.event_type;
  return EVENT_LABELS[canonical] ?? EVENT_LABELS[event.event_type] ?? canonical.replaceAll("_", " ");
}

function sourceLabel(source: string | null | undefined) {
  return registrySourceLabel(source ?? "timeline");
}

function compactValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "нет";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function TimelineEvent({ event }: { event: AdminRegistryTimelineItem }) {
  const related = Object.entries(event.related ?? {}).filter(([, value]) => value !== null && value !== undefined && value !== "");
  const changes = event.changes ?? [];
  return (
    <div className="rounded-lg border border-border px-3 py-3 text-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium text-slate-950">{timelineTypeLabel(event)}</span>
            <Badge tone="neutral">{sourceLabel(event.source)}</Badge>
          </div>
          {event.summary ? <p className="mt-1 text-xs text-slate-500">{event.summary}</p> : null}
        </div>
        <span className="shrink-0 text-xs text-slate-500">{formatDateTime(event.event_at)}</span>
      </div>
      <div className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
        <div>
          <span className="font-semibold text-slate-500">Кто: </span>
          <span>{actorRoleLabel(event.actor_role ?? "system")}{event.actor_id ? ` / ${event.actor_id}` : ""}</span>
        </div>
        <div>
          <span className="font-semibold text-slate-500">Почему: </span>
          <span>{event.reason ?? "не указано"}</span>
        </div>
      </div>
      {changes.length ? (
        <div className="mt-3 rounded-md bg-slate-50 px-3 py-2">
          <p className="text-xs font-semibold uppercase text-slate-400">Что изменилось</p>
          <div className="mt-2 space-y-1">
            {changes.slice(0, 6).map((change, index) => (
              <div className="grid gap-1 text-xs text-slate-700 sm:grid-cols-[120px_1fr]" key={`${event.event_id}-change-${index}`}>
                <span className="font-medium text-slate-600">{compactValue(change.field ?? change.action ?? change.kind ?? "изменение")}</span>
                <span className="break-words">
                  {compactValue(change.before)} → {compactValue(change.after)}
                </span>
              </div>
            ))}
            {changes.length > 6 ? <p className="text-xs text-slate-500">Еще изменений: {changes.length - 6}</p> : null}
          </div>
        </div>
      ) : null}
      {related.length ? (
        <div className="mt-3">
          <p className="text-xs font-semibold uppercase text-slate-400">Затронутые сущности</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {related.map(([key, value]) => (
              <span className="max-w-full rounded-md border border-border px-2 py-1 text-xs text-slate-600" key={`${event.event_id}-${key}`}>
                <span className="font-medium">{RELATED_LABELS[key] ?? key}:</span> <span className="break-all">{compactValue(value)}</span>
              </span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function RegistryDetailDrawer({ registry, selection, onClose }: Props) {
  const timelineQuery = useQuery({
    queryKey: ["admin-registry-timeline", selection?.kind, selection?.id],
    queryFn: () => fetchAdminRegistryTimeline(selection!.kind, selection!.id),
    enabled: Boolean(registry && selection),
    retry: false,
  });
  if (!registry || !selection) return null;
  const device = selection.kind === "device" ? registry.assets.find((item) => item.device_id === selection.id) : null;
  const person = selection.kind === "person" ? registry.people.find((item) => item.person_id === selection.id) : null;
  const binding = selection.kind === "binding" ? (registry.bindings ?? registry.active_bindings).find((item) => item.binding_id === selection.id) : null;
  const claim = selection.kind === "claim" ? registry.registration_claims.find((item) => item.claim_id === selection.id) : null;

  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-xl overflow-y-auto border-l border-border bg-white p-4 shadow-2xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-400">Детали реестра</p>
          <h2 className="text-xl font-semibold text-slate-950">
            {device?.hostname ?? person?.display_name ?? binding?.binding_id ?? claim?.claim_id ?? "Объект"}
          </h2>
        </div>
        <Button aria-label="Закрыть" onClick={onClose} size="icon" variant="ghost">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {device ? (
        <Card>
          <CardHeader>
            <CardTitle>Карточка устройства</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="ID устройства" value={device.device_id} />
              <Field label="Имя ПК" value={device.hostname} />
              <Field label="OS" value={device.os} />
              <Field label="Агент" value={device.agent_version} />
              <Field label="Зарегистрирован" value={device.active_person_name ?? device.owner_name} />
              <Field label="Текущий пользователь ОС" value={device.latest_presence_user ?? device.current_os_user} />
              <Field label="Последняя связь с агентом" value={formatDateTime(device.last_seen_at)} />
            </div>
            <section>
              <p className="mb-2 text-sm font-semibold text-slate-950">Активные привязки</p>
              <div className="space-y-2">
                {(device.active_bindings ?? []).length ? device.active_bindings?.map((item) => (
                  <div className="rounded-lg border border-border px-3 py-2 text-sm" key={item.binding_id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-slate-800">{item.person_name ?? item.person_id}</span>
                      <Badge tone={statusTone(item.relationship_type)}>{relationshipTypeLabel(item.relationship_type)}</Badge>
                    </div>
                    <p className="mt-1 break-all text-xs text-slate-500">{item.binding_id}</p>
                  </div>
                )) : <p className="text-sm text-slate-500">Активных привязок нет.</p>}
              </div>
            </section>
          </CardContent>
        </Card>
      ) : null}

      {person ? (
        <Card>
          <CardHeader>
            <CardTitle>Карточка пользователя</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="ФИО" value={person.full_name} />
              <Field label="Отображаемое имя" value={person.display_name} />
              <Field label="Логин" value={person.login} />
              <Field label="Почта" value={person.email} />
              <Field label="Телефон" value={person.phone} />
              <Field label="Статус" value={registryStatusLabel(person.status)} />
              <Field label="Основные устройства" value={person.primary_device_count ?? 0} />
            </div>
            <section>
              <p className="mb-2 text-sm font-semibold text-slate-950">Идентичности</p>
              <div className="space-y-2">
                {(person.identities ?? []).length ? person.identities?.map((identity) => (
                  <div className="rounded-lg border border-border px-3 py-2 text-sm" key={identity.identity_id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-slate-800">{identity.provider}</span>
                      <Badge tone={identity.verified ? "success" : "warning"}>{identity.verified ? "Подтверждена" : "Не подтверждена"}</Badge>
                    </div>
                    <p className="mt-1 break-all text-xs text-slate-500">{identity.identifier}</p>
                  </div>
                )) : <p className="text-sm text-slate-500">Идентичностей пока нет.</p>}
              </div>
            </section>
          </CardContent>
        </Card>
      ) : null}

      {binding ? (
        <Card>
          <CardHeader>
            <CardTitle>Карточка привязки</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="ID привязки" value={binding.binding_id} />
            <Field label="Устройство" value={binding.hostname ?? binding.device_id} />
            <Field label="Пользователь" value={binding.person_name ?? binding.person_id} />
            <Field label="Тип" value={relationshipTypeLabel(binding.relationship_type)} />
            <Field label="Статус" value={registryStatusLabel(binding.status)} />
            <Field label="Источник" value={registrySourceLabel(binding.source)} />
            <Field label="Подтвердил" value={binding.confirmed_by_admin} />
            <Field label="Подтверждена" value={formatDateTime(binding.confirmed_at)} />
          </CardContent>
        </Card>
      ) : null}


      {claim ? (
        <Card>
          <CardHeader>
            <CardTitle>Заявка регистрации</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="ID заявки" value={claim.claim_id} />
            <Field label="Устройство" value={claim.device_id} />
            <Field label="Пользователь" value={claim.person_name ?? claim.person_id} />
            <Field label="Статус" value={registryStatusLabel(claim.status)} />
            <Field label="Тип" value={relationshipTypeLabel(claim.relationship_type)} />
            <Field label="Конфликт" value={claim.conflict_reason} />
          </CardContent>
        </Card>
      ) : null}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle>История</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {timelineQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем историю...</p> : null}
          {(timelineQuery.data?.items ?? []).length ? timelineQuery.data?.items.map((event) => (
            <TimelineEvent event={event} key={event.event_id} />
          )) : timelineQuery.isLoading ? null : <p className="text-sm text-slate-500">Событий пока нет.</p>}
        </CardContent>
      </Card>
    </aside>
  );
}
