import type { ReactNode } from "react";
import { AlertTriangle, ArrowUpRight, Fingerprint, KeyRound, Link2, Monitor, ShieldCheck, UserCheck, Workflow } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { StatTile } from "../../../components/ui/stat-tile";
import type { AdminRegistryPayload } from "../api";
import { qualityIssueDescription, qualityIssueTitle, relationshipTypeLabel, registryStatusLabel, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  registry: AdminRegistryPayload;
  onSelect: (selection: RegistrySelection) => void;
  onFixIssue: (issue: AdminRegistryPayload["data_quality"][number]) => void;
};

type QueueItem = {
  id: string;
  title: string;
  description: string;
  badge?: string;
  tone: "brand" | "danger" | "info" | "neutral" | "success" | "warning";
  openLabel?: string;
  open?: () => void;
};

type ScenarioQueue = {
  key: string;
  title: string;
  description: string;
  count: number;
  icon: ReactNode;
  tone: QueueItem["tone"];
  actions: string[];
  emptyText: string;
  items: QueueItem[];
};

const pendingClaimStatuses = new Set(["pending_user_confirmation", "pending_admin_review", "user_confirmed", "self_reported"]);

function deviceLabel(device: AdminRegistryPayload["assets"][number]): string {
  return device.hostname ?? device.name ?? device.device_id ?? device.id;
}

function personLabel(person: AdminRegistryPayload["people"][number]): string {
  return person.full_name ?? person.display_name ?? person.login ?? person.person_id;
}

function claimLabel(claim: AdminRegistryPayload["registration_claims"][number]): string {
  return claim.person_name ?? String(claim.profile_snapshot.display_name ?? claim.profile_snapshot.login ?? claim.device_id);
}

function ScenarioQueueCard({ queue }: { queue: ScenarioQueue }) {
  return (
    <section className="flex min-h-[260px] flex-col rounded-lg border border-border bg-white px-4 py-4" data-testid={`registry-queue-${queue.key}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <span className="mt-0.5 rounded-lg bg-slate-100 p-2 text-slate-700" aria-hidden="true">
            {queue.icon}
          </span>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-slate-950">{queue.title}</h3>
            <p className="mt-1 text-xs leading-5 text-slate-500">{queue.description}</p>
          </div>
        </div>
        <Badge tone={queue.tone}>{queue.count}</Badge>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {queue.actions.map((action) => (
          <Badge key={action} tone="neutral">{action}</Badge>
        ))}
      </div>

      <div className="mt-4 flex flex-1 flex-col gap-2">
        {queue.items.length ? queue.items.slice(0, 3).map((item) => (
          <div className="rounded-lg border border-slate-200 px-3 py-2 text-sm" key={item.id}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="break-words font-medium text-slate-900">{item.title}</p>
                <p className="mt-1 break-words text-xs leading-5 text-slate-500">{item.description}</p>
              </div>
              {item.badge ? <Badge tone={item.tone}>{item.badge}</Badge> : null}
            </div>
            {item.open ? (
              <Button
                aria-label={item.openLabel}
                className="mt-3"
                leadingIcon={<ArrowUpRight className="h-4 w-4" />}
                onClick={item.open}
                size="sm"
                title="Открыть карточку и timeline связанного объекта"
                variant="outline"
              >
                Открыть
              </Button>
            ) : null}
          </div>
        )) : (
          <p className="rounded-lg border border-dashed border-border px-3 py-4 text-sm text-slate-500">{queue.emptyText}</p>
        )}
        {queue.items.length > 3 ? <p className="text-xs text-slate-500">Еще записей: {queue.items.length - 3}</p> : null}
      </div>
    </section>
  );
}

export function RegistryOverviewTab({ onFixIssue, onSelect, registry }: Props) {
  const summary = registry.summary;
  const pendingClaims = registry.registration_claims.filter((claim) => pendingClaimStatuses.has(claim.status));
  const conflictClaims = registry.registration_claims.filter((claim) => claim.status === "conflict" || Boolean(claim.conflict_reason));
  const conflictClaimIds = new Set(conflictClaims.map((claim) => claim.claim_id));
  const conflictIssues = registry.data_quality.filter((issue) => (
    issue.kind === "registration_conflict" && !conflictClaimIds.has(issue.claim_id ?? issue.object_id)
  ));
  const usersWithoutPrimary = registry.people.filter((person) => (
    person.status !== "archived" && (person.primary_device_count ?? 0) === 0
  ));
  const devicesWithoutOwner = registry.assets.filter((device) => (
    Boolean(device.device_id)
    && !device.active_person_id
    && !device.assigned_person_id
    && !device.owner_name
    && !device.responsible_person_id
    && !device.active_binding_id
  ));
  const incompleteProfiles = registry.people.filter((person) => (
    Boolean(person.profile_completion) && !person.profile_completion?.complete
  ));
  const duplicateIssues = registry.data_quality.filter((issue) => issue.kind === "duplicate_person");
  const unlinkedUiUsers = (registry.ui_users ?? []).filter((user) => user.is_active && !user.linked_person_id);
  const uiUserIssues = registry.data_quality.filter((issue) => issue.kind === "ui_user_unlinked_registry_person");

  const scenarioQueues: ScenarioQueue[] = [
    {
      key: "pending-device-links",
      title: "Ожидают привязки устройства",
      description: "Заявки регистрации, где нужно подтверждение пользователя или администратора.",
      count: pendingClaims.length,
      icon: <Link2 className="h-4 w-4" />,
      tone: pendingClaims.length ? "warning" : "success",
      actions: ["Подтвердить / отклонить", "Открыть заявку", "Открыть timeline"],
      emptyText: "Новых заявок на привязку нет.",
      items: pendingClaims.map((claim) => ({
        id: claim.claim_id,
        title: claimLabel(claim),
        description: `${claim.device_id} · ${relationshipTypeLabel(claim.relationship_type)}`,
        badge: registryStatusLabel(claim.status),
        tone: statusTone(claim.status),
        openLabel: `Открыть заявку ${claim.claim_id} из очереди Ожидают привязки устройства`,
        open: () => onSelect({ kind: "claim", id: claim.claim_id }),
      })),
    },
    {
      key: "ownership-change",
      title: "Смена владельца и конфликты",
      description: "Конфликты регистрации, где администратор решает, передавать ли основного владельца.",
      count: conflictClaims.length + conflictIssues.length,
      icon: <Workflow className="h-4 w-4" />,
      tone: conflictClaims.length || conflictIssues.length ? "danger" : "success",
      actions: ["Transfer preview", "Передать владельца", "Отклонить конфликт"],
      emptyText: "Конфликтов владельца нет.",
      items: [
        ...conflictClaims.map((claim) => ({
          id: claim.claim_id,
          title: claimLabel(claim),
          description: `${claim.device_id} · ${claim.conflict_reason ?? "конфликт привязки"}`,
          badge: registryStatusLabel(claim.status),
          tone: statusTone(claim.status),
          openLabel: `Открыть заявку ${claim.claim_id} из очереди Смена владельца и конфликты`,
          open: () => onSelect({ kind: "claim", id: claim.claim_id }),
        })),
        ...conflictIssues.map((issue) => ({
          id: issue.issue_key,
          title: qualityIssueTitle(issue),
          description: qualityIssueDescription(issue),
          badge: issue.severity,
          tone: issue.severity,
          openLabel: `Открыть проблему ${issue.issue_key} из очереди Смена владельца и конфликты`,
          open: () => onFixIssue(issue),
        })),
      ],
    },
    {
      key: "users-without-primary",
      title: "Пользователи без основного агента",
      description: "Активные люди без primary_user привязки к устройству.",
      count: usersWithoutPrimary.length,
      icon: <UserCheck className="h-4 w-4" />,
      tone: usersWithoutPrimary.length ? "warning" : "success",
      actions: ["Привязать устройство", "Связать UI-аккаунт", "Открыть пользователя"],
      emptyText: "У всех активных пользователей есть основной агент.",
      items: usersWithoutPrimary.map((person) => ({
        id: person.person_id,
        title: personLabel(person),
        description: [person.login, person.department_name, person.location_name].filter(Boolean).join(" · ") || "Контекст не заполнен",
        badge: `${person.primary_device_count ?? 0} ПК`,
        tone: "warning",
        openLabel: `Открыть пользователя ${person.person_id} из очереди Пользователи без основного агента`,
        open: () => onSelect({ kind: "person", id: person.person_id }),
      })),
    },
    {
      key: "devices-without-owner",
      title: "Устройства без владельца",
      description: "Активные ПК без основного пользователя, ответственного или подтвержденной привязки.",
      count: devicesWithoutOwner.length,
      icon: <Monitor className="h-4 w-4" />,
      tone: devicesWithoutOwner.length ? "warning" : "success",
      actions: ["Привязать владельца", "Добавить shared/responsible", "Открыть устройство"],
      emptyText: "Устройства без владельца не найдены.",
      items: devicesWithoutOwner.map((device) => ({
        id: device.device_id ?? device.id,
        title: deviceLabel(device),
        description: [device.device_id, device.latest_presence_user ?? device.current_os_user, device.location_name].filter(Boolean).join(" · ") || "Устройство без контекста",
        badge: registryStatusLabel(device.registration_status ?? "unregistered"),
        tone: statusTone(device.registration_status ?? "unregistered"),
        openLabel: `Открыть устройство ${device.device_id} из очереди Устройства без владельца`,
        open: () => device.device_id && onSelect({ kind: "device", id: device.device_id }),
      })),
    },
    {
      key: "incomplete-profiles",
      title: "Профиль не заполнен",
      description: "Пользователи с блокирующими или обязательными полями профиля.",
      count: incompleteProfiles.length,
      icon: <ShieldCheck className="h-4 w-4" />,
      tone: incompleteProfiles.length ? "warning" : "success",
      actions: ["Открыть профиль", "Проверить поля", "Связать UI-аккаунт"],
      emptyText: "Незавершенных профилей нет.",
      items: incompleteProfiles.map((person) => {
        const missing = person.profile_completion?.missing_fields.map((field) => field.label).join(", ");
        return {
          id: person.person_id,
          title: personLabel(person),
          description: missing ? `Не хватает: ${missing}` : "Профиль требует проверки",
          badge: person.profile_completion?.status ?? "required",
          tone: "warning",
          openLabel: `Открыть пользователя ${person.person_id} из очереди Профиль не заполнен`,
          open: () => onSelect({ kind: "person", id: person.person_id }),
        };
      }),
    },
    {
      key: "duplicate-identities",
      title: "Дубли идентичностей",
      description: "Возможные дубли персон или идентификаторов, требующие слияния через preview.",
      count: duplicateIssues.length,
      icon: <Fingerprint className="h-4 w-4" />,
      tone: duplicateIssues.length ? "warning" : "success",
      actions: ["Слияние через preview", "Проверить identity", "Открыть проблему"],
      emptyText: "Дубли идентичностей не обнаружены.",
      items: duplicateIssues.map((issue) => ({
        id: issue.issue_key,
        title: qualityIssueTitle(issue),
        description: qualityIssueDescription(issue),
        badge: issue.severity,
        tone: issue.severity,
        openLabel: `Открыть проблему ${issue.issue_key} из очереди Дубли идентичностей`,
        open: () => onFixIssue(issue),
      })),
    },
  ];

  const uiAccountQueue: ScenarioQueue = {
    key: "ui-account-link",
    title: "UI-аккаунты без персоны",
    description: "Активные логины без связи с персоной реестра или без проверенной identity.",
    count: unlinkedUiUsers.length + uiUserIssues.length,
    icon: <KeyRound className="h-4 w-4" />,
    tone: unlinkedUiUsers.length || uiUserIssues.length ? "warning" : "success",
    actions: ["Связать UI-аккаунт с персоной", "Сброс / смена UI-пароля", "Проверить роли"],
    emptyText: "Все активные UI-аккаунты связаны с персонами.",
    items: [
      ...unlinkedUiUsers.map((user) => ({
        id: user.user_login,
        title: user.user_login,
        description: `${registryStatusLabel(user.actor_role)} · роль ${user.actor_role}`,
        badge: "UI",
        tone: "warning" as const,
      })),
      ...uiUserIssues.map((issue) => ({
        id: issue.issue_key,
        title: qualityIssueTitle(issue),
        description: qualityIssueDescription(issue),
        badge: issue.severity,
        tone: issue.severity,
        openLabel: `Открыть проблему ${issue.issue_key} из очереди UI-аккаунты без персоны`,
        open: () => onFixIssue(issue),
      })),
    ],
  };

  const actionItems = [
    ...registry.registration_claims.filter((claim) => ["pending_user_confirmation", "pending_admin_review", "conflict", "user_confirmed", "self_reported"].includes(claim.status)).slice(0, 6).map((claim) => ({
      id: claim.claim_id,
      title: claim.person_name ?? claim.device_id,
      description: `${registryStatusLabel(claim.status)} · ${relationshipTypeLabel(claim.relationship_type)}`,
      tone: statusTone(claim.status),
      open: () => onSelect({ kind: "claim", id: claim.claim_id }),
    })),
    ...registry.data_quality.slice(0, 8).map((issue) => ({
      id: `${issue.kind}-${issue.object_id}`,
      title: qualityIssueTitle(issue),
      description: qualityIssueDescription(issue),
      tone: issue.severity,
      open: () => onFixIssue(issue),
    })),
  ];

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-brand-100 bg-brand-50/60 px-4 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase text-brand-700">Администрирование</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">Центр регистрации и привязок</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Очереди собраны по сценариям администратора: регистрация устройства, смена владельца, связь UI-аккаунта с персоной и качество профилей.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <a
              className="inline-flex h-9 items-center justify-center gap-2 rounded-pill border border-brand-200 bg-white px-3 text-sm font-medium text-brand-800 transition-colors hover:bg-brand-50"
              href="/app/admin/access"
              title="Открыть RBAC-пользователей для смены или сброса UI-пароля"
            >
              <KeyRound className="h-4 w-4" />
              Открыть RBAC-пользователей
            </a>
            <a
              className="inline-flex h-9 items-center justify-center gap-2 rounded-pill border border-border bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
              href="/app/admin/device"
              title="Открыть инвентарь устройств для расширенной карточки ПК"
            >
              <Monitor className="h-4 w-4" />
              Инвентарь
            </a>
          </div>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        <StatTile label="Устройств всего" value={String(summary.devices_total ?? summary.assets)} helper="ПК в реестре" />
        <StatTile label="Зарегистрировано" value={String(summary.devices_registered ?? summary.active_bindings)} helper="Есть активная связь" />
        <StatTile label="Без пользователя" value={String(summary.devices_unregistered ?? summary.unregistered_devices)} helper="Требуют действия" />
        <StatTile label="Ожидают подтверждения" value={String(summary.claims_pending ?? summary.registrations_pending)} helper="Заявки регистрации" />
        <StatTile label="Конфликты" value={String(summary.claims_conflict ?? summary.registrations_conflicts)} helper="Нужна ручная проверка" />
        <StatTile label="Активные привязки" value={String(summary.bindings_active ?? summary.active_bindings)} helper="Основные, совместные и ответственные" />
        <StatTile label="Совместные устройства" value={String(summary.shared_devices ?? 0)} helper="Общие рабочие места" />
        <StatTile label="Качество данных" value={String(summary.quality_issues ?? summary.data_quality_issues)} helper="Проблемы для обработки" />
      </div>

      <section className="space-y-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">Очереди по сценариям</h2>
            <p className="text-sm text-slate-500">Карточки ведут в существующие заявки, устройства, пользователей и timeline.</p>
          </div>
          <Badge tone="neutral">{scenarioQueues.reduce((total, queue) => total + queue.count, uiAccountQueue.count)} задач</Badge>
        </div>
        <div className="grid gap-3 xl:grid-cols-2 2xl:grid-cols-3">
          {[...scenarioQueues, uiAccountQueue].map((queue) => (
            <ScenarioQueueCard key={queue.key} queue={queue} />
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-white">
        <div className="border-b border-border px-4 py-3">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-950">
            <AlertTriangle className="h-5 w-5 text-amber-500" />
            Требует действия
          </h2>
        </div>
        <div className="space-y-2 px-4 py-4">
          {actionItems.length ? actionItems.map((item) => (
            <div className="flex flex-col gap-3 rounded-lg border border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between" key={item.id}>
              <div>
                <div className="flex items-center gap-2">
                  <Badge tone={item.tone}>{item.title}</Badge>
                </div>
                <p className="mt-2 text-sm text-slate-600">{item.description}</p>
              </div>
              <Button leadingIcon={<ArrowUpRight className="h-4 w-4" />} onClick={item.open} size="sm" title="Открыть связанную запись реестра" variant="outline">
                Открыть
              </Button>
            </div>
          )) : <p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Очередь действий пуста.</p>}
        </div>
      </section>
    </div>
  );
}
