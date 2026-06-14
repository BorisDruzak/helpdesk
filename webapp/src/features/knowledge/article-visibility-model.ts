import type {
  KnowledgeAudienceExplain,
  KnowledgeAudiencePreview,
  KnowledgeAudienceRule,
  KnowledgeAudienceRuleInput,
  KnowledgeAudienceRuleTargetType,
} from "./api";

type RegistryPerson = {
  person_id?: string;
  id?: string;
  display_name?: string;
  full_name?: string | null;
  email?: string | null;
  login?: string | null;
  department_id?: string | null;
  location_id?: string | null;
  status?: string;
};

type RegistryDepartment = {
  department_id?: string;
  id?: string;
  code?: string | null;
  name: string;
  parent_id?: string | null;
  status?: string;
};

type RegistryLocation = {
  location_id?: string;
  id?: string;
  display_name: string;
  status?: string;
};

type RegistryService = {
  id: string;
  code?: string | null;
  name: string;
  status?: string;
};

type RegistryPayload = {
  people?: RegistryPerson[];
  departments?: RegistryDepartment[];
  locations?: RegistryLocation[];
  services?: RegistryService[];
};

type AudienceGroup = {
  audience_group_id: string;
  code: string;
  name: string;
  status?: string;
};

type AccessGroup = {
  group_id: number;
  code: string;
  name: string;
  is_active?: boolean;
  members?: string[];
};

type VisibilityLookups = {
  registry: RegistryPayload;
  audienceGroups: AudienceGroup[];
  accessGroups: AccessGroup[];
};

type TargetOption = {
  label: string;
  secondary?: string;
  value: string;
};

export const targetTypeOptions: Array<{ label: string; value: KnowledgeAudienceRuleTargetType }> = [
  { label: "Роль", value: "role" },
  { label: "Сотрудник", value: "person" },
  { label: "Подразделение", value: "department" },
  { label: "Подразделение и дочерние", value: "department_tree" },
  { label: "Локация", value: "location" },
  { label: "Группа доступа", value: "access_group" },
  { label: "Аудитория", value: "audience_group" },
  { label: "Сервис", value: "service" },
];

export const visibilityLabels: Record<string, string> = {
  public: "Публичная",
  requester: "Портал заявителя",
  agent_requester_safe: "Агент и заявитель",
  support_internal: "Внутреннее для поддержки",
  admin_internal: "Только администраторы",
  security_restricted: "Ограничено безопасностью",
  auditor_read: "Только аудиторы",
};

const roleOptions: TargetOption[] = [
  { value: "user", label: "Заявитель" },
  { value: "support", label: "Поддержка" },
  { value: "admin", label: "Администратор" },
  { value: "auditor", label: "Аудитор" },
];

function idOf(value: { id?: string | null; department_id?: string | null; location_id?: string | null; person_id?: string | null }) {
  return value.person_id ?? value.department_id ?? value.location_id ?? value.id ?? "";
}

async function readLookup<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.details ?? payload?.error ?? fallbackMessage);
  }
  if (payload?.status === "success" && payload?.data) {
    return payload.data as T;
  }
  return payload as T;
}

export async function fetchVisibilityLookups(): Promise<VisibilityLookups> {
  const [registryResponse, audienceGroupsResponse, accessSummaryResponse] = await Promise.all([
    fetch("/api/web/admin/registry", { credentials: "same-origin" }),
    fetch("/api/web/admin/registry/audience-groups", { credentials: "same-origin" }),
    fetch("/api/web/admin/access/summary", { credentials: "same-origin" }),
  ]);
  const [registry, audienceGroupsPayload, accessSummary] = await Promise.all([
    readLookup<RegistryPayload>(registryResponse, "Не удалось загрузить реестр"),
    readLookup<{ groups?: AudienceGroup[] }>(audienceGroupsResponse, "Не удалось загрузить аудитории"),
    readLookup<{ access_groups?: AccessGroup[] }>(accessSummaryResponse, "Не удалось загрузить группы доступа"),
  ]);
  return {
    registry,
    audienceGroups: audienceGroupsPayload.groups ?? [],
    accessGroups: accessSummary.access_groups ?? [],
  };
}

export function ruleToDraft(rule: KnowledgeAudienceRule): KnowledgeAudienceRuleInput {
  return {
    rule_id: rule.rule_id ?? null,
    target_type: rule.target_type,
    target_id: rule.target_id,
    effect: "allow",
    include_children: rule.include_children ?? rule.target_type === "department_tree",
    priority: rule.priority ?? 10,
    status: rule.status ?? "active",
    reason: rule.reason ?? null,
    metadata_json: rule.metadata_json ?? {},
  };
}

export function targetOptionsFor(targetType: KnowledgeAudienceRuleTargetType, lookups: VisibilityLookups | undefined): TargetOption[] {
  const registry = lookups?.registry ?? {};
  if (targetType === "role") {
    return roleOptions;
  }
  if (targetType === "person") {
    return (registry.people ?? [])
      .filter((person) => person.status !== "archived")
      .map((person) => ({
        value: idOf(person),
        label: person.display_name || person.full_name || person.email || person.login || idOf(person),
        secondary: person.email ?? person.login ?? undefined,
      }));
  }
  if (targetType === "department" || targetType === "department_tree") {
    return (registry.departments ?? [])
      .filter((department) => department.status !== "archived")
      .map((department) => ({
        value: idOf(department),
        label: department.name,
        secondary: department.code ?? undefined,
      }));
  }
  if (targetType === "location") {
    return (registry.locations ?? [])
      .filter((location) => location.status !== "archived")
      .map((location) => ({ value: idOf(location), label: location.display_name }));
  }
  if (targetType === "access_group") {
    return (lookups?.accessGroups ?? [])
      .filter((group) => group.is_active !== false)
      .map((group) => ({ value: String(group.group_id), label: group.name, secondary: group.code }));
  }
  if (targetType === "audience_group") {
    return (lookups?.audienceGroups ?? [])
      .filter((group) => group.status !== "archived")
      .map((group) => ({ value: group.audience_group_id, label: group.name, secondary: group.code }));
  }
  return (registry.services ?? [])
    .filter((service) => service.status !== "archived")
    .map((service) => ({ value: service.code || service.id, label: service.name, secondary: service.code ?? undefined }));
}

function departmentTreeIds(departments: RegistryDepartment[], rootId: string) {
  const ids = new Set([rootId]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const department of departments) {
      const departmentId = idOf(department);
      if (department.parent_id && ids.has(department.parent_id) && !ids.has(departmentId)) {
        ids.add(departmentId);
        changed = true;
      }
    }
  }
  return ids;
}

function targetLabel(rule: Pick<KnowledgeAudienceRuleInput, "target_id" | "target_type">, lookups: VisibilityLookups | undefined) {
  const option = targetOptionsFor(rule.target_type, lookups).find((item) => item.value === rule.target_id);
  return option?.label ?? rule.target_id;
}

export function ruleLabel(rule: KnowledgeAudienceRuleInput, lookups: VisibilityLookups | undefined) {
  const label = targetLabel(rule, lookups);
  if (rule.target_type === "person") return `Сотрудник: ${label}`;
  if (rule.target_type === "department") return `Подразделение: ${label}`;
  if (rule.target_type === "department_tree") return `Подразделение и дочерние: ${label}`;
  if (rule.target_type === "location") return `Локация: ${label}`;
  if (rule.target_type === "access_group") return `Группа доступа: ${label}`;
  if (rule.target_type === "audience_group") return `Аудитория: ${label}`;
  if (rule.target_type === "service") return `Сервис: ${label}`;
  return `Роль: ${label}`;
}

export function pluralPeople(count: number) {
  if (count % 10 === 1 && count % 100 !== 11) return `${count} человек`;
  return `${count} человека`;
}

export function estimateAudience(rules: KnowledgeAudienceRuleInput[], lookups: VisibilityLookups | undefined) {
  const people = (lookups?.registry.people ?? []).filter((person) => person.status !== "archived");
  const departments = lookups?.registry.departments ?? [];
  const personIds = new Set<string>();
  const matchedLabels = new Set<string>();
  for (const rule of rules.filter((item) => (item.status ?? "active") === "active")) {
    if (rule.target_type === "person") {
      const person = people.find((item) => idOf(item) === rule.target_id || item.email === rule.target_id || item.login === rule.target_id);
      if (person) personIds.add(idOf(person));
    }
    if (rule.target_type === "department") {
      people.filter((person) => person.department_id === rule.target_id).forEach((person) => personIds.add(idOf(person)));
      matchedLabels.add(ruleLabel(rule, lookups));
    }
    if (rule.target_type === "department_tree") {
      const departmentIds = departmentTreeIds(departments, rule.target_id);
      people.filter((person) => person.department_id && departmentIds.has(person.department_id)).forEach((person) => personIds.add(idOf(person)));
      matchedLabels.add(ruleLabel(rule, lookups));
    }
    if (rule.target_type === "location") {
      people.filter((person) => person.location_id === rule.target_id).forEach((person) => personIds.add(idOf(person)));
      matchedLabels.add(ruleLabel(rule, lookups));
    }
    if (rule.target_type === "access_group") {
      const group = lookups?.accessGroups.find((item) => String(item.group_id) === rule.target_id || item.code === rule.target_id);
      const members = new Set(group?.members ?? []);
      people.filter((person) => (person.login && members.has(person.login)) || (person.email && members.has(person.email))).forEach((person) => personIds.add(idOf(person)));
      matchedLabels.add(ruleLabel(rule, lookups));
    }
    if (rule.target_type === "audience_group" || rule.target_type === "service" || rule.target_type === "role") {
      matchedLabels.add(ruleLabel(rule, lookups));
    }
  }
  return { count: personIds.size, matchedLabels: Array.from(matchedLabels) };
}

export function decisionLabel(result: KnowledgeAudiencePreview | KnowledgeAudienceExplain | null) {
  if (!result) return "";
  return result.decision.allowed ? "Можно видеть" : "Скрыто";
}

export function internalVisibilityWarning(visibility: string) {
  return ["support_internal", "admin_internal", "security_restricted", "auditor_read"].includes(visibility);
}
