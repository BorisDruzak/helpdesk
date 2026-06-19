import type {
  AuthenticatedRequesterTicket,
  RequestFormDefinition,
  RequestFormField,
  RequestFormPack,
  RequesterBootstrap,
  RequesterConsent,
  RequesterDevice,
  RequesterOnBehalfPerson,
  RequesterProfile,
  RequesterProfileSchemaField,
} from "./types";

export const REQUESTER_REQUEST_FIELD_TYPES = [
  "text",
  "textarea",
  "select",
  "multi_select",
  "radio",
  "checkbox",
  "number",
  "date",
  "datetime",
  "file",
  "user_picker",
  "department_picker",
  "location_picker",
  "device_picker",
  "service_picker",
  "url",
  "phone",
  "email",
] as const satisfies readonly RequestFormField["type"][];

export const REQUESTER_PROFILE_FIELD_TYPES = [
  "text",
  "textarea",
  "select",
  "phone",
  "email",
  "url",
  "number",
  "date",
  "checkbox",
] as const satisfies readonly RequesterProfileSchemaField["type"][];

type ForbiddenVisibleTerm = {
  term: string;
  pattern: RegExp;
  reason: string;
};

export const REQUESTER_FORBIDDEN_VISIBLE_TERMS: readonly ForbiddenVisibleTerm[] = [
  { term: "Requester", pattern: /\brequester\b/i, reason: "Use Russian requester-facing terms." },
  { term: "user", pattern: /\buser\b/i, reason: "Use account/profile/person labels instead of raw role text." },
  { term: "ticket", pattern: /\bticket\b/i, reason: "Use Обращение." },
  { term: "pairing", pattern: /\bpairing\b/i, reason: "Use Привязка устройства." },
  { term: "binding", pattern: /\bbinding\b/i, reason: "Use Привязка устройства." },
  { term: "claim", pattern: /\bclaim\b/i, reason: "Hide registration internals." },
  { term: "session", pattern: /\bsession\b/i, reason: "Hide account-session internals." },
  { term: "registry person", pattern: /\bregistry person\b/i, reason: "Use Профиль or Сотрудник." },
  { term: "verified", pattern: /\bverified\b/i, reason: "Hide identity verification internals." },
  { term: "not verified", pattern: /\bnot verified\b/i, reason: "Hide identity verification internals." },
  { term: "profile not linked", pattern: /\bprofile not linked\b/i, reason: "Use action-oriented profile guidance." },
  { term: "*_id", pattern: /\b[a-z][a-z0-9]*_id\b/i, reason: "Hide raw storage identifiers." },
  {
    term: "raw UUID",
    pattern: /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/i,
    reason: "Hide raw UUID values.",
  },
  { term: "backend enum", pattern: /\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b/, reason: "Map enums to Russian labels." },
  { term: "policy key", pattern: /\b[a-z]+(?:\.[a-z0-9_]+)+\b/i, reason: "Hide policy keys." },
  { term: "trace id", pattern: /\btrace id\b/i, reason: "Hide observer trace internals." },
  { term: "operation id", pattern: /\boperation id\b/i, reason: "Hide operation internals." },
  { term: "consent id", pattern: /\bconsent id\b/i, reason: "Hide consent internals." },
  { term: "artifact id", pattern: /\bartifact id\b/i, reason: "Hide artifact internals." },
];

export type RequesterBaselineFixtureId =
  | "complete_profile_primary_device"
  | "incomplete_profile_no_device"
  | "complete_profile_no_device"
  | "pending_device_link"
  | "multiple_devices_with_offline_primary"
  | "waiting_request_and_consent"
  | "close_rate_reopen"
  | "on_behalf_allowed"
  | "on_behalf_forbidden"
  | "archived_user";

export const REQUESTER_BASELINE_FIXTURE_IDS = [
  "complete_profile_primary_device",
  "incomplete_profile_no_device",
  "complete_profile_no_device",
  "pending_device_link",
  "multiple_devices_with_offline_primary",
  "waiting_request_and_consent",
  "close_rate_reopen",
  "on_behalf_allowed",
  "on_behalf_forbidden",
  "archived_user",
] as const satisfies readonly RequesterBaselineFixtureId[];

export type RequesterBaselineFixture = {
  id: RequesterBaselineFixtureId;
  title: string;
  description: string;
  bootstrap: RequesterBootstrap;
  forms: RequestFormPack;
  tickets: AuthenticatedRequesterTicket[];
  consents: RequesterConsent[];
  onBehalfPeople: RequesterOnBehalfPerson[];
  visibleText: string[];
  expected: {
    archivedBlocked?: boolean;
    canCreateNormalRequest: boolean;
    lifecycleActions?: Array<"close" | "rate" | "reopen">;
    onBehalf?: "allowed" | "forbidden" | "not_applicable";
    pendingConsentCount: number;
    setupHelpOnly?: "profile" | "device" | "none";
  };
};

const completeProfile: RequesterProfile = {
  person_id: "person-complete",
  display_name: "Иван Петров",
  full_name: "Иван Петров",
  email: "ivan.petrov@example.test",
  phone: "+7 000 100-10-10",
  department_id: "department-it",
  location_id: "location-office-7",
  status: "active",
};

const primaryDevice: RequesterDevice = {
  device_id: "device-primary",
  hostname: "OFFICE-PC-01",
  os: "Windows",
  agent_version: "3.1.72",
  online: true,
  binding_status: "active",
  relationship_type: "primary_user",
  available_actions: { create_ticket: true, view_tickets: true },
};

const offlinePrimaryDevice: RequesterDevice = {
  ...primaryDevice,
  device_id: "device-primary-offline",
  hostname: "OFFICE-PC-OFFLINE",
  online: false,
};

const secondaryDevice: RequesterDevice = {
  device_id: "device-secondary",
  hostname: "OFFICE-PC-02",
  os: "Windows",
  agent_version: "3.1.72",
  online: true,
  binding_status: "active",
  relationship_type: "secondary_user",
};

const normalForm: RequestFormDefinition = {
  key: "normal_access",
  request_template_key: "normal_access",
  title: "Обычное обращение",
  request_kind: "request",
  fields: [
    { key: "summary", label: "Кратко опишите проблему", type: "text", required: true },
    { key: "details", label: "Подробности", type: "textarea", required: false },
  ],
};

const profileHelpForm: RequestFormDefinition = {
  key: "profile_completion_help",
  request_template_key: "profile_completion_help",
  title: "Помощь с заполнением профиля",
  request_kind: "profile_completion_help",
  availability_policy: {
    available_without_completed_profile: true,
    available_without_agent_binding: true,
    requires_manual_triage: true,
    contact_required: true,
  },
  fields: [{ key: "contact_phone", label: "Телефон для связи", type: "phone", required: true }],
};

const deviceHelpForm: RequestFormDefinition = {
  key: "agent_binding_help",
  request_template_key: "agent_binding_help",
  title: "Помощь с привязкой устройства",
  request_kind: "agent_binding_help",
  availability_policy: {
    available_without_completed_profile: true,
    available_without_agent_binding: true,
    requires_manual_triage: true,
    contact_required: true,
  },
  fields: [{ key: "contact_phone", label: "Телефон для связи", type: "phone", required: true }],
};

const onBehalfAllowedForm: RequestFormDefinition = {
  ...normalForm,
  key: "on_behalf_allowed",
  request_template_key: "on_behalf_allowed",
  title: "Обращение от имени сотрудника",
  on_behalf_policy: {
    allowed: true,
    affected_person_required: true,
    reason_required: true,
    diagnostic_target: "affected_person_primary_agent",
  },
};

const onBehalfForbiddenForm: RequestFormDefinition = {
  ...normalForm,
  key: "on_behalf_forbidden",
  request_template_key: "on_behalf_forbidden",
  title: "Личное обращение",
  on_behalf_policy: { allowed: false },
};

function formPack(forms: RequestFormDefinition[]): RequestFormPack {
  return { pack_key: "request_forms", version: "phase-a-baseline", forms };
}

function bootstrap(overrides: Partial<RequesterBootstrap>): RequesterBootstrap {
  return {
    workspace: "requester",
    profile: completeProfile,
    profile_completion: {
      complete: true,
      status: "complete",
      setup_path: "/app/requester/profile/setup",
      required_fields: [],
      missing_fields: [],
      blocks: { ticket_create: false, ticket_preview: false, device_binding_confirmation: false },
    },
    profile_schema: {
      schema_key: "requester_profile",
      fields: [],
      custom_fields: [],
      required_fields: [],
    },
    devices: [primaryDevice],
    active_bindings: [
      {
        binding_id: "binding-primary",
        device_id: primaryDevice.device_id,
        relationship_type: "primary_user",
        status: "active",
      },
    ],
    pending_registration_claims: [],
    open_ticket_count: 0,
    tickets_requiring_user_action_count: 0,
    pending_consent_count: 0,
    recent_tickets: [],
    feature_flags: { requester_ticket_create: true, requester_no_device_create: false },
    ...overrides,
  };
}

const waitingTicket: AuthenticatedRequesterTicket = {
  ticket_id: "ticket-waiting",
  ticket_code: "T-000101",
  title: "Нужно подтвердить решение",
  requester_status: "waiting_user",
  requester_status_label: "Требуется ваше действие",
};

const resolvedTicket: AuthenticatedRequesterTicket = {
  ticket_id: "ticket-resolved",
  ticket_code: "T-000102",
  title: "Проверить результат работы",
  requester_status: "resolved",
  requester_status_label: "Решение предложено",
};

const pendingConsent: RequesterConsent = {
  consent_id: "consent-screen-view",
  subject_type: "remote_assist",
  subject_id: "remote-assist-screen-view",
  status: "pending",
  risk_level: "remote_view",
  title: "Разрешить просмотр экрана",
  description: "Специалист просит временный просмотр экрана для обращения.",
};

const affectedPerson: RequesterOnBehalfPerson = {
  person_id: "person-affected",
  display_name: "Мария Смирнова",
  full_name: "Мария Смирнова",
  department: { id: "department-it", name: "ИТ" },
  location: { id: "location-office-7", display_name: "Офис 7" },
  primary_agent: { status: "available", online: true },
};

export const REQUESTER_BASELINE_FIXTURES: Record<RequesterBaselineFixtureId, RequesterBaselineFixture> = {
  complete_profile_primary_device: {
    id: "complete_profile_primary_device",
    title: "Complete profile with primary device",
    description: "Normal requester can create a standard request from the primary device.",
    bootstrap: bootstrap({}),
    forms: formPack([normalForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Кабинет пользователя", "Создать обращение", "Основное устройство", "Обычное обращение"],
    expected: { canCreateNormalRequest: true, onBehalf: "not_applicable", pendingConsentCount: 0, setupHelpOnly: "none" },
  },
  incomplete_profile_no_device: {
    id: "incomplete_profile_no_device",
    title: "Incomplete profile without device",
    description: "Normal request creation is blocked, but profile setup help remains available.",
    bootstrap: bootstrap({
      profile: null,
      profile_completion: {
        complete: false,
        status: "required",
        setup_path: "/app/requester/profile/setup",
        required_fields: [{ key: "full_name", label: "ФИО" }],
        missing_fields: [{ key: "full_name", label: "ФИО" }],
        blocks: { ticket_create: true, ticket_preview: true, device_binding_confirmation: false },
      },
      devices: [],
      active_bindings: [],
      feature_flags: { requester_ticket_create: false, requester_no_device_create: false },
    }),
    forms: formPack([profileHelpForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Заполните профиль", "Помощь с заполнением профиля", "Создать обращение пока нельзя"],
    expected: { canCreateNormalRequest: false, onBehalf: "not_applicable", pendingConsentCount: 0, setupHelpOnly: "profile" },
  },
  complete_profile_no_device: {
    id: "complete_profile_no_device",
    title: "Complete profile without device",
    description: "Normal request creation is blocked by missing device, but device-link help remains available.",
    bootstrap: bootstrap({
      devices: [],
      active_bindings: [],
      feature_flags: { requester_ticket_create: false, requester_no_device_create: false },
    }),
    forms: formPack([deviceHelpForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Привяжите устройство", "Помощь с привязкой устройства", "Основное устройство не найдено"],
    expected: { canCreateNormalRequest: false, onBehalf: "not_applicable", pendingConsentCount: 0, setupHelpOnly: "device" },
  },
  pending_device_link: {
    id: "pending_device_link",
    title: "Pending device link",
    description: "Requester sees a pending device review without technical registration terms.",
    bootstrap: bootstrap({
      devices: [],
      active_bindings: [],
      pending_registration_claims: [{ claim_id: "claim-pending", device_id: "device-pending", status: "pending_admin_review" }],
      feature_flags: { requester_ticket_create: false, requester_no_device_create: false },
    }),
    forms: formPack([deviceHelpForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Устройство ожидает проверки администратора", "Мы сообщим, когда привязка будет готова"],
    expected: { canCreateNormalRequest: false, onBehalf: "not_applicable", pendingConsentCount: 0, setupHelpOnly: "device" },
  },
  multiple_devices_with_offline_primary: {
    id: "multiple_devices_with_offline_primary",
    title: "Multiple devices with offline primary",
    description: "Requester sees the primary device state but cannot override the server-resolved target.",
    bootstrap: bootstrap({
      devices: [offlinePrimaryDevice, secondaryDevice],
      active_bindings: [
        {
          binding_id: "binding-offline-primary",
          device_id: offlinePrimaryDevice.device_id,
          relationship_type: "primary_user",
          status: "active",
        },
        {
          binding_id: "binding-secondary",
          device_id: secondaryDevice.device_id,
          relationship_type: "secondary_user",
          status: "active",
        },
      ],
    }),
    forms: formPack([normalForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Основное устройство не в сети", "Другое устройство доступно", "Цель диагностики определит сервер"],
    expected: { canCreateNormalRequest: true, onBehalf: "not_applicable", pendingConsentCount: 0, setupHelpOnly: "none" },
  },
  waiting_request_and_consent: {
    id: "waiting_request_and_consent",
    title: "Waiting request and pending consent",
    description: "Requester has a pending action and a consent card.",
    bootstrap: bootstrap({
      open_ticket_count: 1,
      tickets_requiring_user_action_count: 1,
      pending_consent_count: 1,
      recent_tickets: [waitingTicket],
    }),
    forms: formPack([normalForm]),
    tickets: [waitingTicket],
    consents: [pendingConsent],
    onBehalfPeople: [],
    visibleText: ["Требуется ваше действие", "Разрешить просмотр экрана", "Ответить специалисту"],
    expected: { canCreateNormalRequest: true, onBehalf: "not_applicable", pendingConsentCount: 1, setupHelpOnly: "none" },
  },
  close_rate_reopen: {
    id: "close_rate_reopen",
    title: "Close, rate, and reopen",
    description: "Resolved request exposes only allowed lifecycle actions.",
    bootstrap: bootstrap({ recent_tickets: [resolvedTicket] }),
    forms: formPack([normalForm]),
    tickets: [resolvedTicket],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Решение предложено", "Подтвердить решение", "Оценить работу", "Открыть повторно"],
    expected: {
      canCreateNormalRequest: true,
      lifecycleActions: ["close", "rate", "reopen"],
      onBehalf: "not_applicable",
      pendingConsentCount: 0,
      setupHelpOnly: "none",
    },
  },
  on_behalf_allowed: {
    id: "on_behalf_allowed",
    title: "On-behalf allowed",
    description: "Selected form allows choosing an affected employee and requires a reason.",
    bootstrap: bootstrap({}),
    forms: formPack([onBehalfAllowedForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [affectedPerson],
    visibleText: ["Сотрудник, у которого проблема", "Причина обращения от имени сотрудника", "Мария Смирнова"],
    expected: { canCreateNormalRequest: true, onBehalf: "allowed", pendingConsentCount: 0, setupHelpOnly: "none" },
  },
  on_behalf_forbidden: {
    id: "on_behalf_forbidden",
    title: "On-behalf forbidden",
    description: "Selected form is personal only and must not expose affected-employee controls.",
    bootstrap: bootstrap({}),
    forms: formPack([onBehalfForbiddenForm]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Личное обращение", "Опишите свою проблему"],
    expected: { canCreateNormalRequest: true, onBehalf: "forbidden", pendingConsentCount: 0, setupHelpOnly: "none" },
  },
  archived_user: {
    id: "archived_user",
    title: "Archived user",
    description: "Archived actor is fail-closed and cannot use requester actions.",
    bootstrap: bootstrap({
      profile: { ...completeProfile, status: "archived" },
      devices: [],
      active_bindings: [],
      feature_flags: { requester_ticket_create: false, requester_no_device_create: false },
    }),
    forms: formPack([]),
    tickets: [],
    consents: [],
    onBehalfPeople: [],
    visibleText: ["Доступ к кабинету остановлен", "Обратитесь к администратору"],
    expected: { archivedBlocked: true, canCreateNormalRequest: false, onBehalf: "not_applicable", pendingConsentCount: 0 },
  },
};

export type RequesterForbiddenTermMatch = {
  term: string;
  text: string;
  reason: string;
};

export function assertNoRequesterForbiddenTerms(text: string | readonly string[]): RequesterForbiddenTermMatch[] {
  const items = Array.isArray(text) ? text : [text];
  const matches: RequesterForbiddenTermMatch[] = [];
  for (const item of items) {
    for (const forbidden of REQUESTER_FORBIDDEN_VISIBLE_TERMS) {
      if (forbidden.pattern.test(item)) {
        matches.push({ term: forbidden.term, text: item, reason: forbidden.reason });
      }
    }
  }
  return matches;
}
