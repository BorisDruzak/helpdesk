import type {
  AccessCatalogPayload,
  AccessEffectivePayload,
  AccessGroupItem,
  AccessPermissionGroup,
  AccessPermissionItem,
  AccessQueueGrant,
  AccessQueueItem,
  AccessUserItem,
} from "./api";

export type AccessTab = "overview" | "users" | "groups" | "queues" | "roles" | "catalog" | "audit";

export type PermissionSource = "role" | "group" | "role_group" | "unknown";

export type EffectivePermissionRow = AccessPermissionItem & {
  domain: string;
  source: PermissionSource;
  sourceLabel: string;
};

export type GroupDraft = {
  members: string[];
  permissions: string[];
  queues: Array<{ queue_id: number; role_in_queue: string | null }>;
};

export type AccessChangeDiff = {
  addedMembers: string[];
  addedPermissions: AccessPermissionItem[];
  addedQueues: Array<{ queue_id: number; queue_name: string; role_in_queue: string | null }>;
  affectedUsersCount: number;
  highRiskAdded: AccessPermissionItem[];
  hasChanges: boolean;
  removedMembers: string[];
  removedPermissions: AccessPermissionItem[];
  removedQueues: Array<{ queue_id: number; queue_name: string; role_in_queue: string | null }>;
};

export const ACCESS_TABS: Array<{ value: AccessTab; label: string }> = [
  { value: "overview", label: "Обзор" },
  { value: "users", label: "Пользователи" },
  { value: "groups", label: "Группы" },
  { value: "queues", label: "Очереди" },
  { value: "roles", label: "Роли" },
  { value: "catalog", label: "Каталог прав" },
  { value: "audit", label: "Аудит" },
];

export function normalizeText(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

export function riskLabel(risk: string): string {
  if (risk === "high") {
    return "Высокий риск";
  }
  if (risk === "normal") {
    return "Обычный риск";
  }
  return "Риск не классифицирован";
}

export function riskTone(risk: string): "danger" | "neutral" | "warning" {
  return risk === "high" ? "warning" : "neutral";
}

export function workspaceLabel(workspace: string): string {
  const labels: Record<string, string> = {
    admin: "Администрирование",
    requester: "Портал заявителя",
    support: "Поддержка",
  };
  return labels[workspace] ?? workspace;
}

export function statusLabel(isActive: boolean): string {
  return isActive ? "Активен" : "Отключён";
}

export function buildPermissionMap(catalog: AccessCatalogPayload): Map<string, AccessPermissionItem & { domain: string }> {
  const result = new Map<string, AccessPermissionItem & { domain: string }>();
  for (const group of catalog.groups) {
    for (const permission of group.permissions) {
      result.set(permission.code, { ...permission, domain: group.label });
    }
  }
  return result;
}

export function findPermission(catalog: AccessCatalogPayload, code: string): AccessPermissionItem & { domain: string } {
  return (
    buildPermissionMap(catalog).get(code) ?? {
      code,
      description: "Описание не передано API.",
      domain: "Другое",
      label: code,
      risk: "unknown",
    }
  );
}

export function rolePermissionSet(catalog: AccessCatalogPayload, actorRole: string): Set<string> {
  const role = catalog.roles.find((item) => item.code === actorRole);
  return new Set(role?.permissions ?? []);
}

export function groupPermissionSet(groups: AccessGroupItem[], groupCodes: string[]): Set<string> {
  const allowedCodes = new Set(groupCodes);
  const result = new Set<string>();
  for (const group of groups) {
    if (!allowedCodes.has(group.code)) {
      continue;
    }
    for (const permission of group.permissions) {
      result.add(permission);
    }
  }
  return result;
}

export function buildEffectivePermissionRows(
  catalog: AccessCatalogPayload,
  accessGroups: AccessGroupItem[],
  effective: AccessEffectivePayload,
): EffectivePermissionRow[] {
  const permissionMap = buildPermissionMap(catalog);
  const rolePermissions = rolePermissionSet(catalog, effective.actor_role);
  const groupPermissions = groupPermissionSet(accessGroups, effective.groups);

  return effective.permissions.map((code) => {
    const known = permissionMap.get(code) ?? {
      code,
      description: "Описание не передано API.",
      domain: "Другое",
      label: code,
      risk: "unknown",
    };
    const fromRole = rolePermissions.has(code);
    const fromGroup = groupPermissions.has(code);
    const source: PermissionSource = fromRole && fromGroup ? "role_group" : fromRole ? "role" : fromGroup ? "group" : "unknown";
    return {
      ...known,
      source,
      sourceLabel: sourceLabel(source),
    };
  });
}

export function sourceLabel(source: PermissionSource): string {
  const labels: Record<PermissionSource, string> = {
    group: "Источник: группа",
    role: "Источник: роль",
    role_group: "Источник: роль + группа",
    unknown: "Источник: не уточнён API",
  };
  return labels[source];
}

export function filterUsers(users: AccessUserItem[], query: string, role: string, status: string, flag: string): AccessUserItem[] {
  const normalized = normalizeText(query);
  return users.filter((user) => {
    const matchesQuery =
      !normalized ||
      [user.user_login, user.actor_role, user.role_label, ...user.groups].some((value) => normalizeText(value).includes(normalized));
    const matchesRole = role === "all" || user.actor_role === role;
    const matchesStatus =
      status === "all" || (status === "active" && user.is_active) || (status === "disabled" && !user.is_active);
    const matchesFlag =
      flag === "all" ||
      (flag === "groups" && user.groups.length > 0) ||
      (flag === "queues" && user.queue_count > 0) ||
      (flag === "elevated" && ["admin", "support"].includes(user.actor_role));
    return matchesQuery && matchesRole && matchesStatus && matchesFlag;
  });
}

export function filterGroups(groups: AccessGroupItem[], query: string): AccessGroupItem[] {
  const normalized = normalizeText(query);
  if (!normalized) {
    return groups;
  }
  return groups.filter((group) =>
    [group.code, group.name, group.description, ...group.permissions, ...group.members].some((value) =>
      normalizeText(value).includes(normalized),
    ),
  );
}

export function filterQueues(queues: AccessQueueItem[], query: string, status: string): AccessQueueItem[] {
  const normalized = normalizeText(query);
  return queues.filter((queue) => {
    const matchesQuery =
      !normalized || [queue.queue_code, queue.queue_name].some((value) => normalizeText(value).includes(normalized));
    const matchesStatus =
      status === "all" || (status === "active" && queue.is_active) || (status === "disabled" && !queue.is_active);
    return matchesQuery && matchesStatus;
  });
}

export function filterPermissionGroups(groups: AccessPermissionGroup[], query: string, selectedCodes?: Set<string>): AccessPermissionGroup[] {
  const normalized = normalizeText(query);
  return groups
    .map((group) => ({
      ...group,
      permissions: group.permissions.filter((permission) => {
        const matchesQuery =
          !normalized ||
          [group.code, group.label, permission.code, permission.label, permission.description, permission.risk].some((value) =>
            normalizeText(value).includes(normalized),
          );
        const matchesSelected = !selectedCodes || selectedCodes.has(permission.code);
        return matchesQuery && matchesSelected;
      }),
    }))
    .filter((group) => group.permissions.length > 0);
}

export function buildGroupDraft(group: AccessGroupItem): GroupDraft {
  return {
    members: [...group.members].sort(),
    permissions: [...group.permissions].sort(),
    queues: group.queue_grants
      .map((queue) => ({ queue_id: queue.queue_id, role_in_queue: queue.role_in_queue }))
      .sort((left, right) => left.queue_id - right.queue_id),
  };
}

export function buildAccessChangeDiff(
  group: AccessGroupItem,
  draft: GroupDraft,
  catalog: AccessCatalogPayload,
  queues: AccessQueueItem[],
): AccessChangeDiff {
  const current = buildGroupDraft(group);
  const addedPermissionCodes = difference(draft.permissions, current.permissions);
  const removedPermissionCodes = difference(current.permissions, draft.permissions);
  const addedMembers = difference(draft.members, current.members);
  const removedMembers = difference(current.members, draft.members);
  const currentQueueKeys = current.queues.map(queueKey);
  const draftQueueKeys = draft.queues.map(queueKey);
  const addedQueueKeys = difference(draftQueueKeys, currentQueueKeys);
  const removedQueueKeys = difference(currentQueueKeys, draftQueueKeys);
  const addedPermissions = addedPermissionCodes.map((code) => findPermission(catalog, code));
  const removedPermissions = removedPermissionCodes.map((code) => findPermission(catalog, code));
  const addedQueues = addedQueueKeys.map((key) => queueItemFromKey(key, queues));
  const removedQueues = removedQueueKeys.map((key) => queueItemFromKey(key, queues));
  const highRiskAdded = addedPermissions.filter((permission) => permission.risk === "high");
  const hasChanges =
    addedPermissions.length > 0 ||
    removedPermissions.length > 0 ||
    addedMembers.length > 0 ||
    removedMembers.length > 0 ||
    addedQueues.length > 0 ||
    removedQueues.length > 0;
  return {
    addedMembers,
    addedPermissions,
    addedQueues,
    affectedUsersCount: new Set([...group.members, ...draft.members]).size,
    hasChanges,
    highRiskAdded,
    removedMembers,
    removedPermissions,
    removedQueues,
  };
}

export function queueGrantsForQueue(groups: AccessGroupItem[], queueId: number): AccessGroupItem[] {
  return groups.filter((group) => group.queue_grants.some((grant) => grant.queue_id === queueId));
}

export function effectiveGroupUserCount(groups: AccessGroupItem[], queueId: number): number {
  const users = new Set<string>();
  for (const group of queueGrantsForQueue(groups, queueId)) {
    for (const member of group.members) {
      users.add(member);
    }
  }
  return users.size;
}

export function directQueueGrantLabel(grant: AccessQueueGrant): string {
  return grant.role_in_queue ? `${grant.queue_name} · ${grant.role_in_queue}` : grant.queue_name;
}

function difference(left: string[], right: string[]): string[] {
  const rightSet = new Set(right);
  return left.filter((item) => !rightSet.has(item)).sort();
}

function queueKey(queue: { queue_id: number; role_in_queue: string | null }): string {
  return `${queue.queue_id}:${queue.role_in_queue ?? ""}`;
}

function queueItemFromKey(key: string, queues: AccessQueueItem[]) {
  const [queueIdRaw, roleInQueueRaw] = key.split(":");
  const queueId = Number(queueIdRaw);
  const queue = queues.find((item) => item.queue_id === queueId);
  return {
    queue_id: queueId,
    queue_name: queue?.queue_name ?? String(queueId),
    role_in_queue: roleInQueueRaw || null,
  };
}
