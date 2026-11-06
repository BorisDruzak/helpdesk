import type { AccessCatalogPayload, AccessSummaryPayload } from "../access-control/api";
import type { AdminRegistryPayload } from "../admin/api";

export const registryFixture: AdminRegistryPayload = {
  summary: { assets: 0, people: 2, locations: 0, departments: 0, services: 0, vendors: 0, registrations_pending: 0, registrations_conflicts: 0, unregistered_devices: 0, active_bindings: 0, stale_bindings: 0, data_quality_issues: 0, suggestions: 0 },
  assets: [], locations: [], departments: [], services: [], vendors: [], data_quality: [], suggestions: [], registration_claims: [], active_bindings: [],
  people: [
    { id: "person-marina", person_id: "person-marina", display_name: "Марина Заваруха", full_name: "Заваруха Марина", phone: "123", email: "marina@example.test", department_id: null, location_id: null, department_name: "Общий отдел", location_name: "Администрация", source: "manual", status: "active", updated_at: null },
    { id: "person-ivan", person_id: "person-ivan", display_name: "Иван Петров", full_name: "Петров Иван", phone: null, email: null, department_id: null, location_id: null, department_name: "ИТ", location_name: null, source: "manual", status: "active", updated_at: null },
  ],
  ui_users: [{ user_login: "unlinked.marina", actor_role: "user", is_active: true, failed_attempts: 0, locked_until: null, last_login_at: null, created_at: null, updated_at: null, linked_person_id: null, linked_person_name: null, linked_identity_id: null, linked_identity_verified: false }],
};

export const catalogFixture: AccessCatalogPayload = {
  version: "test", roles: [
    { code: "user", label: "Пользователь", permissions: ["workspace.requester.view"] },
    { code: "support", label: "Сотрудник техподдержки", permissions: ["workspace.support.view"] },
    { code: "admin", label: "Администратор", permissions: ["workspace.admin.view"] },
    { code: "auditor", label: "Аудитор", permissions: [] },
  ], groups: [],
};

export const summaryFixture: AccessSummaryPayload = {
  version: "test", notes: [], users: [{ user_login: "unlinked.marina", display_name: null, actor_role: "user", role_label: "Пользователь", is_active: true, groups: [], queue_count: 0 }],
  queues: [
    { queue_id: 7, queue_code: "l1", queue_name: "ServiceDesk L1", is_active: true, members_count: 0 },
    { queue_id: 8, queue_code: "l2", queue_name: "Вторая линия", is_active: true, members_count: 0 },
    { queue_id: 9, queue_code: "old", queue_name: "Старая очередь", is_active: false, members_count: 0 },
  ],
  access_groups: [{ group_id: 10, code: "specialists", name: "Специалисты", description: "Рабочая группа", is_active: true, permissions: [], members: [], queue_grants: [{ queue_id: 8, queue_code: "l2", queue_name: "Вторая линия", role_in_queue: null }] }],
};
