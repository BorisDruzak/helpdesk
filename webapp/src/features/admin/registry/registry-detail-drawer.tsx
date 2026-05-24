import { X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { fetchAdminRegistryTimeline, type AdminRegistryPayload, type AdminRegistryTimelineItem } from "../api";
import { formatDateTime, statusTone, type RegistrySelection } from "./registry-utils";

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
  identity_added: "Identity добавлен",
  identity_verified: "Identity подтвержден",
  identity_deleted: "Identity удален",
  binding_created: "Привязка создана",
  admin_binding_created: "Привязка создана администратором",
  binding_activated: "Привязка активирована",
  binding_revoked: "Привязка отозвана",
  binding_transferred: "Привязка передана",
  shared_user_added: "Добавлен shared user",
  responsible_assigned: "Назначен ответственный",
  location_merged: "Локации объединены",
  department_merged: "Подразделения объединены",
  people_merged: "Пользователи объединены",
  person_merged: "Пользователи объединены",
  bulk_action_applied: "Bulk action выполнен",
  policy_changed: "Политика изменена",
  registry_policy_updated: "Политика реестра изменена",
  confirmed_binding_session_created: "Account session создана",
  account_session_revoked: "Account session отозвана",
  account_session_revoked_due_to_binding_change: "Session отозвана из-за привязки",
};

const RELATED_LABELS: Record<string, string> = {
  object_type: "Тип объекта",
  object_id: "Object ID",
  device_id: "Device",
  person_id: "Person",
  binding_id: "Binding",
  claim_id: "Claim",
  session_id: "Session",
  request_id: "Request",
  ticket_id: "Ticket",
  identity_id: "Identity",
  location_id: "Location",
  department_id: "Department",
};

function timelineTypeLabel(event: AdminRegistryTimelineItem) {
  const canonical = event.canonical_event_type ?? event.event_type;
  return EVENT_LABELS[canonical] ?? EVENT_LABELS[event.event_type] ?? canonical.replaceAll("_", " ");
}

function sourceLabel(source: string | null | undefined) {
  if (source === "registry_admin") return "admin";
  if (source === "registration") return "registration";
  if (source === "account") return "account";
  return source ?? "timeline";
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
          <span>{event.actor_role ?? "system"}{event.actor_id ? ` / ${event.actor_id}` : ""}</span>
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
                <span className="font-medium text-slate-600">{compactValue(change.field ?? change.action ?? change.kind ?? "change")}</span>
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
    queryFn: () => fetchAdminRegistryTimeline(selection!.kind === "session" ? "account_session" : selection!.kind, selection!.id),
    enabled: Boolean(registry && selection),
    retry: false,
  });
  if (!registry || !selection) return null;
  const device = selection.kind === "device" ? registry.assets.find((item) => item.device_id === selection.id) : null;
  const person = selection.kind === "person" ? registry.people.find((item) => item.person_id === selection.id) : null;
  const binding = selection.kind === "binding" ? (registry.bindings ?? registry.active_bindings).find((item) => item.binding_id === selection.id) : null;
  const session = selection.kind === "session" ? (registry.account_sessions ?? []).find((item) => item.session_id === selection.id) : null;
  const claim = selection.kind === "claim" ? registry.registration_claims.find((item) => item.claim_id === selection.id) : null;

  return (
    <aside className="fixed inset-y-0 right-0 z-40 w-full max-w-xl overflow-y-auto border-l border-border bg-white p-4 shadow-2xl">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-slate-400">Registry detail</p>
          <h2 className="text-xl font-semibold text-slate-950">
            {device?.hostname ?? person?.display_name ?? binding?.binding_id ?? session?.session_id ?? claim?.claim_id ?? "Объект"}
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
              <Field label="Device ID" value={device.device_id} />
              <Field label="Hostname" value={device.hostname} />
              <Field label="OS" value={device.os} />
              <Field label="Agent" value={device.agent_version} />
              <Field label="Зарегистрирован" value={device.active_person_name ?? device.owner_name} />
              <Field label="Presence" value={device.latest_presence_user ?? device.current_os_user} />
              <Field label="Последний handshake" value={formatDateTime(device.last_seen_at)} />
              <Field label="Account sessions" value={device.active_sessions_count ?? 0} />
            </div>
            <section>
              <p className="mb-2 text-sm font-semibold text-slate-950">Активные привязки</p>
              <div className="space-y-2">
                {(device.active_bindings ?? []).length ? device.active_bindings?.map((item) => (
                  <div className="rounded-lg border border-border px-3 py-2 text-sm" key={item.binding_id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-slate-800">{item.person_name ?? item.person_id}</span>
                      <Badge tone={statusTone(item.relationship_type)}>{item.relationship_type}</Badge>
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
              <Field label="Display name" value={person.display_name} />
              <Field label="Login" value={person.login} />
              <Field label="Email" value={person.email} />
              <Field label="Phone" value={person.phone} />
              <Field label="Статус" value={person.status} />
              <Field label="Primary devices" value={person.primary_device_count ?? 0} />
              <Field label="Active sessions" value={person.active_session_count ?? 0} />
            </div>
            <section>
              <p className="mb-2 text-sm font-semibold text-slate-950">Identities</p>
              <div className="space-y-2">
                {(person.identities ?? []).length ? person.identities?.map((identity) => (
                  <div className="rounded-lg border border-border px-3 py-2 text-sm" key={identity.identity_id}>
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-medium text-slate-800">{identity.provider}</span>
                      <Badge tone={identity.verified ? "success" : "warning"}>{identity.verified ? "verified" : "unverified"}</Badge>
                    </div>
                    <p className="mt-1 break-all text-xs text-slate-500">{identity.identifier}</p>
                  </div>
                )) : <p className="text-sm text-slate-500">Identity пока нет.</p>}
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
            <Field label="Binding ID" value={binding.binding_id} />
            <Field label="Device" value={binding.hostname ?? binding.device_id} />
            <Field label="User" value={binding.person_name ?? binding.person_id} />
            <Field label="Type" value={binding.relationship_type} />
            <Field label="Status" value={binding.status} />
            <Field label="Source" value={binding.source} />
            <Field label="Confirmed by" value={binding.confirmed_by_admin} />
            <Field label="Confirmed at" value={formatDateTime(binding.confirmed_at)} />
            <Field label="Active sessions" value={binding.active_sessions_count ?? 0} />
          </CardContent>
        </Card>
      ) : null}

      {session ? (
        <Card>
          <CardHeader>
            <CardTitle>Account session</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="Session ID" value={session.session_id} />
            <Field label="Device" value={session.device_id} />
            <Field label="Account" value={session.display_name ?? session.login} />
            <Field label="Mode" value={session.account_mode} />
            <Field label="Status" value={session.verification_status} />
            <Field label="Base binding" value={session.base_binding_id} />
            <Field label="Created" value={formatDateTime(session.created_at)} />
            <Field label="Revoked" value={formatDateTime(session.revoked_at)} />
          </CardContent>
        </Card>
      ) : null}

      {claim ? (
        <Card>
          <CardHeader>
            <CardTitle>Заявка регистрации</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="Claim ID" value={claim.claim_id} />
            <Field label="Device" value={claim.device_id} />
            <Field label="Person" value={claim.person_name ?? claim.person_id} />
            <Field label="Status" value={claim.status} />
            <Field label="Type" value={claim.relationship_type} />
            <Field label="Conflict" value={claim.conflict_reason} />
          </CardContent>
        </Card>
      ) : null}
      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Timeline</CardTitle>
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
