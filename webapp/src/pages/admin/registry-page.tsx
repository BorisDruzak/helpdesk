import { Download, Plus, RefreshCcw, Search, ShieldCheck, Upload, UserPlus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type Dispatch, type SetStateAction } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import {
  addAdminRegistrySharedUser,
  adminRegistryExportUrl,
  applyAdminRegistryImport,
  archiveAdminRegistryDepartment,
  archiveAdminRegistryLocation,
  approveAdminAccountLoginRequest,
  approveAdminRegistrationClaim,
  assignAdminRegistryResponsible,
  bindAdminRegistryDevicePerson,
  bulkAssignAdminRegistryDeviceDepartment,
  bulkAssignAdminRegistryDeviceLocation,
  bulkAssignAdminRegistryPeopleDepartment,
  bulkRevokeAdminRegistryAccountSessions,
  bulkRevokeAdminRegistryDeviceAccountSessions,
  createAdminRegistryDepartment,
  createAdminRegistryLocation,
  createAdminRegistryPerson,
  createAdminRegistryPersonIdentity,
  fetchAdminAccountLoginRequests,
  fetchAdminRegistry,
  mergeAdminRegistryDepartments,
  mergeAdminRegistryLocations,
  mergeAdminRegistryPeople,
  previewAdminRegistryDepartmentsMerge,
  previewAdminRegistryDeviceOwnerTransfer,
  previewAdminRegistryImport,
  previewAdminRegistryLocationsMerge,
  previewAdminRegistryPeopleMerge,
  rejectAdminAccountLoginRequest,
  rejectAdminRegistrationClaim,
  revokeAdminDeviceAccountSession,
  revokeAdminDeviceUserBinding,
  transferAdminRegistryDeviceOwner,
  updateAdminRegistryQualityIssue,
  updateAdminRegistryDepartment,
  updateAdminRegistryLocation,
  updateAdminRegistryPerson,
  type AdminDeviceAccountSession,
  type AdminDeviceUserBinding,
  type AdminRegistrationClaim,
  type AdminRegistryBulkResponse,
  type AdminRegistryPayload,
} from "../../features/admin/api";
import { RegistryAccountSessionsTab } from "../../features/admin/registry/registry-account-sessions-tab";
import { RegistryBindPersonDialog, type BindPersonDialogState } from "../../features/admin/registry/registry-bind-person-dialog";
import { RegistryBindingsTab } from "../../features/admin/registry/registry-bindings-tab";
import { RegistryBulkActions, type RegistryBulkAction } from "../../features/admin/registry/registry-bulk-actions";
import { RegistryDepartmentsTab } from "../../features/admin/registry/registry-departments-tab";
import { RegistryDetailDrawer } from "../../features/admin/registry/registry-detail-drawer";
import { RegistryDevicesTab } from "../../features/admin/registry/registry-devices-tab";
import { RegistryIdentityDialog, type IdentityDialogState } from "../../features/admin/registry/registry-identity-dialog";
import { RegistryImportDialog } from "../../features/admin/registry/registry-import-dialog";
import { RegistryLocationsTab } from "../../features/admin/registry/registry-locations-tab";
import { RegistryMergePeopleDialog } from "../../features/admin/registry/registry-merge-people-dialog";
import { RegistryOverviewTab } from "../../features/admin/registry/registry-overview-tab";
import { RegistryPeopleTab } from "../../features/admin/registry/registry-people-tab";
import { RegistryPersonEditDialog, type PersonEditDialogState } from "../../features/admin/registry/registry-person-edit-dialog";
import { RegistryPoliciesTab } from "../../features/admin/registry/registry-policies-tab";
import { RegistryQualityTab } from "../../features/admin/registry/registry-quality-tab";
import { RegistryRequestsTab } from "../../features/admin/registry/registry-requests-tab";
import { RegistryTransferDeviceDialog } from "../../features/admin/registry/registry-transfer-device-dialog";
import { filterRegistryPayload, type RegistrySelection, type RegistryTabKey } from "../../features/admin/registry/registry-utils";
import { cn } from "../../shared/ui/cn";

const tabs: Array<{ key: RegistryTabKey; label: string; p1?: boolean }> = [
  { key: "overview", label: "Обзор" },
  { key: "devices", label: "Устройства" },
  { key: "people", label: "Пользователи" },
  { key: "bindings", label: "Привязки" },
  { key: "requests", label: "Заявки" },
  { key: "account_sessions", label: "Аккаунт-сессии" },
  { key: "quality", label: "Качество данных" },
  { key: "locations", label: "Локации", p1: true },
  { key: "departments", label: "Подразделения", p1: true },
  { key: "policies", label: "Политики", p1: true },
];

function PlaceholderTab({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-sm text-slate-500">
          P1: базовое чтение уже доступно в payload; CRUD, merge duplicates и policy editor будут добавлены отдельным безопасным проходом.
        </p>
      </CardContent>
    </Card>
  );
}

function registryActionErrorMessage(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : fallback;
  if (message.includes("user confirmation required before approval")) {
    return "Нужно подтверждение пользователя на агенте. Для ручного обхода используйте «Админское подтверждение» с причиной.";
  }
  return message;
}

export function AdminRegistryPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<RegistryTabKey>("overview");
  const [selection, setSelection] = useState<RegistrySelection>(null);
  const [bindDialog, setBindDialog] = useState<BindPersonDialogState>(null);
  const [transferDialog, setTransferDialog] = useState<{ deviceId: string; hostname?: string | null } | null>(null);
  const [identityDialog, setIdentityDialog] = useState<IdentityDialogState>(null);
  const [personDialog, setPersonDialog] = useState<PersonEditDialogState>(null);
  const [mergePersonId, setMergePersonId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [selectedPersonIds, setSelectedPersonIds] = useState<string[]>([]);
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);
  const [bulkResult, setBulkResult] = useState<AdminRegistryBulkResponse | null>(null);

  const registryQuery = useQuery({
    queryKey: ["admin-registry"],
    queryFn: fetchAdminRegistry,
    retry: false,
    refetchInterval: 15_000,
  });
  const accountLoginRequestsQuery = useQuery({
    queryKey: ["admin-registry-account-login-requests"],
    queryFn: () => fetchAdminAccountLoginRequests("pending_verification"),
    retry: false,
    refetchInterval: 15_000,
  });

  const invalidateRegistry = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-registry-account-login-requests"] });
  };

  const mutation = useMutation({
    mutationFn: async (operation: () => Promise<void>) => operation(),
    onError: (error) => setActionError(registryActionErrorMessage(error, "Не удалось выполнить действие")),
    onSuccess: async () => {
      setActionError(null);
      setBindDialog(null);
      setTransferDialog(null);
      setIdentityDialog(null);
      setPersonDialog(null);
      setMergePersonId(null);
      setImportOpen(false);
      await invalidateRegistry();
    },
  });

  const bulkMutation = useMutation({
    mutationFn: async (operation: () => Promise<AdminRegistryBulkResponse>) => operation(),
    onError: (error) => setActionError(registryActionErrorMessage(error, "Bulk action failed")),
    onSuccess: async (result) => {
      setActionError(null);
      setBulkResult(result);
      await invalidateRegistry();
    },
  });

  const importMutation = useMutation({
    mutationFn: applyAdminRegistryImport,
    onError: (error) => setActionError(registryActionErrorMessage(error, "Import apply failed")),
    onSuccess: async () => {
      setActionError(null);
      await invalidateRegistry();
    },
  });

  const registry = registryQuery.data ?? null;
  const visibleRegistry = useMemo(
    () => (registry ? filterRegistryPayload(registry, query) : null),
    [query, registry]
  );
  const pendingLoginRequests = accountLoginRequestsQuery.data?.items ?? registry?.account_login_requests ?? [];
  const toggleSelected = (id: string, setter: Dispatch<SetStateAction<string[]>>) => {
    setter((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  };
  const toggleVisibleSelected = (ids: string[], setter: Dispatch<SetStateAction<string[]>>) => {
    setter((current) => {
      const visible = new Set(ids);
      const allSelected = ids.length > 0 && ids.every((id) => current.includes(id));
      if (allSelected) {
        return current.filter((id) => !visible.has(id));
      }
      return Array.from(new Set([...current, ...ids]));
    });
  };
  const selectedBulkCount =
    tab === "devices" ? selectedDeviceIds.length :
    tab === "people" ? selectedPersonIds.length :
    tab === "account_sessions" ? selectedSessionIds.length :
    0;
  const bulkActions: RegistryBulkAction[] = useMemo(() => {
    if (tab === "devices") {
      return [
        { key: "devices.assign_location", label: "Assign location" },
        { key: "devices.assign_department", label: "Assign department" },
        { key: "devices.revoke_account_sessions", label: "Revoke sessions" },
      ];
    }
    if (tab === "people") {
      return [{ key: "people.assign_department", label: "Assign department" }];
    }
    if (tab === "account_sessions") {
      return [{ key: "account_sessions.revoke", label: "Revoke sessions" }];
    }
    return [];
  }, [tab]);
  const clearCurrentBulkSelection = () => {
    if (tab === "devices") {
      setSelectedDeviceIds([]);
    } else if (tab === "people") {
      setSelectedPersonIds([]);
    } else if (tab === "account_sessions") {
      setSelectedSessionIds([]);
    }
  };

  const handleBulkAction = (operation: string) => {
    if (operation === "devices.assign_location") {
      const locationId = window.prompt("Location ID", "") ?? "";
      const reason = window.prompt("Reason", "Bulk assign device location") ?? "";
      if (locationId.trim() && reason.trim()) {
        bulkMutation.mutate(() => bulkAssignAdminRegistryDeviceLocation({ ids: selectedDeviceIds, location_id: locationId.trim(), reason: reason.trim() }));
      }
      return;
    }
    if (operation === "devices.assign_department") {
      const departmentId = window.prompt("Department ID", "") ?? "";
      const reason = window.prompt("Reason", "Bulk assign device department") ?? "";
      if (departmentId.trim() && reason.trim()) {
        bulkMutation.mutate(() => bulkAssignAdminRegistryDeviceDepartment({ ids: selectedDeviceIds, department_id: departmentId.trim(), reason: reason.trim() }));
      }
      return;
    }
    if (operation === "devices.revoke_account_sessions") {
      const reason = window.prompt("Reason", "Bulk revoke device account sessions") ?? "";
      if (reason.trim()) {
        bulkMutation.mutate(() => bulkRevokeAdminRegistryDeviceAccountSessions(selectedDeviceIds, reason.trim()));
      }
      return;
    }
    if (operation === "people.assign_department") {
      const departmentId = window.prompt("Department ID", "") ?? "";
      const reason = window.prompt("Reason", "Bulk assign people department") ?? "";
      if (departmentId.trim() && reason.trim()) {
        bulkMutation.mutate(() => bulkAssignAdminRegistryPeopleDepartment({ ids: selectedPersonIds, department_id: departmentId.trim(), reason: reason.trim() }));
      }
      return;
    }
    if (operation === "account_sessions.revoke") {
      const reason = window.prompt("Reason", "Bulk revoke account sessions") ?? "";
      if (reason.trim()) {
        bulkMutation.mutate(() => bulkRevokeAdminRegistryAccountSessions(selectedSessionIds, reason.trim()));
      }
    }
  };

  const runWithReason = (label: string, fallback: string, action: (reason: string) => Promise<void>) => {
    const reason = window.prompt(label, fallback) ?? "";
    if (!reason.trim()) {
      return;
    }
    mutation.mutate(() => action(reason.trim()));
  };

  const handleFixIssue = (issue: AdminRegistryPayload["data_quality"][number]) => {
    if (issue.kind === "asset_missing_confirmed_user" && issue.device_id) {
      setBindDialog({ deviceId: issue.device_id, mode: "primary_user", title: "Привязать пользователя", replaceExisting: false });
      return;
    }
    if (issue.kind === "registration_conflict" && issue.claim_id) {
      setSelection({ kind: "claim", id: issue.claim_id });
      setTab("requests");
      return;
    }
    if (issue.kind === "binding_stale" && issue.binding_id) {
      const binding = registry?.active_bindings.find((item) => item.binding_id === issue.binding_id)
        ?? registry?.bindings?.find((item) => item.binding_id === issue.binding_id);
      if (binding) {
        runWithReason("Причина отзыва stale-привязки", "Устаревшая привязка", (reason) => revokeAdminDeviceUserBinding(binding.binding_id, reason));
      }
      return;
    }
    if (issue.kind === "missing_identity" && issue.person_id) {
      const person = registry?.people.find((item) => item.person_id === issue.person_id);
      if (person) {
        setIdentityDialog({ personId: person.person_id, personName: person.display_name });
      }
      return;
    }
    if (issue.kind === "duplicate_person" && issue.person_id) {
      setMergePersonId(issue.person_id);
      return;
    }
    if ((issue.kind === "missing_location" || issue.kind === "asset_missing_location") && issue.device_id) {
      setTab("devices");
      setSelection({ kind: "device", id: issue.device_id });
    }
  };

  const revokeAllDeviceSessions = (device: AdminRegistryPayload["assets"][number]) => {
    const sessions = (registry?.account_sessions ?? []).filter((session) =>
      session.device_id === device.device_id && session.verification_status !== "revoked"
    );
    if (!sessions.length) {
      return;
    }
    runWithReason("Причина отзыва account sessions", "Администратор отозвал сессии устройства", async (reason) => {
      await Promise.all(sessions.map((session) => revokeAdminDeviceAccountSession(session.session_id, reason)));
    });
  };

  const bindPersonToKnownDevice = (person: AdminRegistryPayload["people"][number]) => {
    const deviceId = window.prompt("Device ID для привязки пользователя", "") ?? "";
    if (!deviceId.trim()) {
      return;
    }
    setBindDialog({ deviceId: deviceId.trim(), mode: "primary_user", title: `Привязать ${person.display_name} к устройству`, replaceExisting: false });
  };

  const exportType =
    tab === "people" ? "people" :
    tab === "bindings" ? "bindings" :
    tab === "account_sessions" ? "sessions" :
    tab === "locations" ? "locations" :
    tab === "departments" ? "departments" :
    tab === "quality" ? "quality" :
    "devices";

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setPersonDialog({})} size="sm" variant="outline">
              Пользователь
            </Button>
            <Button leadingIcon={<UserPlus className="h-4 w-4" />} onClick={() => setBindDialog({ deviceId: "", mode: "primary_user", title: "Привязать устройство", replaceExisting: false })} size="sm" variant="outline">
              Привязать устройство
            </Button>
            <Button leadingIcon={<ShieldCheck className="h-4 w-4" />} onClick={() => setTab("quality")} size="sm" variant="outline">
              Проверка качества
            </Button>
            <Button leadingIcon={<Download className="h-4 w-4" />} onClick={() => { window.location.href = adminRegistryExportUrl(exportType); }} size="sm" variant="ghost">
              Экспорт
            </Button>
            <Button leadingIcon={<Upload className="h-4 w-4" />} onClick={() => setImportOpen(true)} size="sm" variant="ghost">
              Импорт
            </Button>
            <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void registryQuery.refetch()} size="sm">
              Обновить
            </Button>
          </>
        }
        description="Device-user bindings, account sessions, registration claims, people identities and data-quality actions in one operator workspace."
        eyebrow="Admin workspace"
        title="Registry Management Center"
      />

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <CardTitle>Операционный реестр</CardTitle>
            <div className="flex min-w-[320px] items-center gap-2">
              <Search className="h-4 w-4 text-slate-400" />
              <SearchField
                onChange={(event) => setQuery(event.target.value)}
                placeholder="ФИО, login, email, phone, device_id, hostname, cabinet, binding_id, session_id"
                value={query}
              />
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
                {item.label}{item.p1 ? " · P1" : ""}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? <p className="text-sm text-rose-600">{actionError}</p> : null}
          {registryQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем Registry Management Center...</p> : null}
          {registryQuery.isError ? (
            <p className="text-sm text-rose-600">
              {registryQuery.error instanceof Error ? registryQuery.error.message : "Не удалось загрузить реестры."}
            </p>
          ) : null}
          <RegistryBulkActions
            actions={bulkActions}
            busy={bulkMutation.isPending}
            result={bulkResult}
            selectedCount={selectedBulkCount}
            onAction={handleBulkAction}
            onClearResult={() => setBulkResult(null)}
            onClearSelection={clearCurrentBulkSelection}
          />

          {visibleRegistry && tab === "overview" ? <RegistryOverviewTab registry={visibleRegistry} onFixIssue={handleFixIssue} onSelect={setSelection} /> : null}
          {visibleRegistry && tab === "devices" ? (
            <RegistryDevicesTab
              devices={visibleRegistry.assets}
              onBind={(deviceId) => setBindDialog({ deviceId, mode: "primary_user", title: "Привязать пользователя", replaceExisting: false })}
              onResponsible={(deviceId) => setBindDialog({ deviceId, mode: "responsible", title: "Назначить ответственного", replaceExisting: true })}
              onRevokeSessions={revokeAllDeviceSessions}
              onSelect={setSelection}
              onShared={(deviceId) => setBindDialog({ deviceId, mode: "shared_user", title: "Добавить shared user", replaceExisting: false })}
              onToggleSelection={(deviceId) => toggleSelected(deviceId, setSelectedDeviceIds)}
              onToggleVisibleSelection={(deviceIds) => toggleVisibleSelected(deviceIds, setSelectedDeviceIds)}
              onTransfer={(device) => device.device_id && setTransferDialog({ deviceId: device.device_id, hostname: device.hostname })}
              selectedIds={selectedDeviceIds}
            />
          ) : null}
          {visibleRegistry && tab === "people" ? (
            <RegistryPeopleTab
              people={visibleRegistry.people}
              onAddIdentity={(person) => setIdentityDialog({ personId: person.person_id, personName: person.display_name })}
              onBindToDevice={bindPersonToKnownDevice}
              onEdit={(person) => setPersonDialog({ person })}
              onMerge={(person) => setMergePersonId(person.person_id)}
              onSelect={setSelection}
              onToggleSelection={(personId) => toggleSelected(personId, setSelectedPersonIds)}
              onToggleVisibleSelection={(personIds) => toggleVisibleSelected(personIds, setSelectedPersonIds)}
              selectedIds={selectedPersonIds}
            />
          ) : null}
          {visibleRegistry && tab === "bindings" ? (
            <RegistryBindingsTab
              bindings={visibleRegistry.bindings ?? visibleRegistry.active_bindings}
              onRevoke={(binding: AdminDeviceUserBinding) => runWithReason("Причина отзыва привязки", "Отозвано администратором", (reason) => revokeAdminDeviceUserBinding(binding.binding_id, reason))}
              onSelect={setSelection}
              onTransferDevice={(deviceId) => setTransferDialog({ deviceId })}
            />
          ) : null}
          {visibleRegistry && tab === "requests" ? (
            <RegistryRequestsTab
              claims={visibleRegistry.registration_claims}
              loginRequests={pendingLoginRequests}
              onApproveClaim={(claim: AdminRegistrationClaim, replaceExisting = false, override = false) => {
                if (override) {
                  runWithReason("Причина админского подтверждения", "Проверено администратором", (reason) => approveAdminRegistrationClaim(claim.claim_id, replaceExisting, true, reason));
                } else {
                  mutation.mutate(() => approveAdminRegistrationClaim(claim.claim_id, replaceExisting));
                }
              }}
              onApproveLoginRequest={(request) => mutation.mutate(() => approveAdminAccountLoginRequest(request.request_id))}
              onRejectClaim={(claim) => runWithReason("Причина отклонения заявки", "Данные не подтверждены", (reason) => rejectAdminRegistrationClaim(claim.claim_id, reason))}
              onRejectLoginRequest={(request) => runWithReason("Причина отклонения входа", "Не подтверждено администратором", (reason) => rejectAdminAccountLoginRequest(request.request_id, reason))}
              onSelect={setSelection}
            />
          ) : null}
          {visibleRegistry && tab === "account_sessions" ? (
            <RegistryAccountSessionsTab
              sessions={visibleRegistry.account_sessions ?? []}
              onRevoke={(session: AdminDeviceAccountSession) => runWithReason("Причина отзыва account session", "Отозвано администратором", (reason) => revokeAdminDeviceAccountSession(session.session_id, reason))}
              onSelect={setSelection}
              onToggleSelection={(sessionId) => toggleSelected(sessionId, setSelectedSessionIds)}
              onToggleVisibleSelection={(sessionIds) => toggleVisibleSelected(sessionIds, setSelectedSessionIds)}
              selectedIds={selectedSessionIds}
            />
          ) : null}
          {visibleRegistry && tab === "quality" ? (
            <RegistryQualityTab
              issues={visibleRegistry.data_quality}
              onFix={handleFixIssue}
              onIgnore={(issue, reason) => mutation.mutate(() => updateAdminRegistryQualityIssue({ issue_key: issue.issue_key, action: "ignore", reason }).then(() => undefined))}
              onSelect={setSelection}
              onSnooze={(issue, reason, days) => mutation.mutate(() => updateAdminRegistryQualityIssue({ issue_key: issue.issue_key, action: "snooze", reason, days }).then(() => undefined))}
              suggestions={visibleRegistry.suggestions}
            />
          ) : null}
          {visibleRegistry && tab === "locations" ? (
            <RegistryLocationsTab
              locations={visibleRegistry.locations}
              onArchive={(location) => runWithReason("Причина архивации локации", "Локация больше не используется", (reason) => archiveAdminRegistryLocation(location.location_id ?? location.id, reason))}
              onMergePreview={(masterId, duplicateId) => previewAdminRegistryLocationsMerge({ master_location_id: masterId, duplicate_location_id: duplicateId })}
              onMerge={(masterId, duplicateId, reason) => mutation.mutate(() => mergeAdminRegistryLocations({ master_location_id: masterId, duplicate_location_id: duplicateId, reason }))}
              onSave={(payload) => mutation.mutate(() => (
                payload.locationId
                  ? updateAdminRegistryLocation(payload.locationId, payload)
                  : createAdminRegistryLocation(payload)
              ))}
            />
          ) : null}
          {visibleRegistry && tab === "departments" ? (
            <RegistryDepartmentsTab
              departments={visibleRegistry.departments}
              onArchive={(department) => runWithReason("Причина архивации подразделения", "Подразделение больше не используется", (reason) => archiveAdminRegistryDepartment(department.department_id ?? department.id, reason))}
              onMergePreview={(masterId, duplicateId) => previewAdminRegistryDepartmentsMerge({ master_department_id: masterId, duplicate_department_id: duplicateId })}
              onMerge={(masterId, duplicateId, reason) => mutation.mutate(() => mergeAdminRegistryDepartments({ master_department_id: masterId, duplicate_department_id: duplicateId, reason }))}
              onSave={(payload) => mutation.mutate(() => (
                payload.departmentId
                  ? updateAdminRegistryDepartment(payload.departmentId, payload)
                  : createAdminRegistryDepartment(payload)
              ))}
            />
          ) : null}
          {tab === "policies" ? <RegistryPoliciesTab /> : null}
        </CardContent>
      </Card>

      <RegistryDetailDrawer registry={registry} selection={selection} onClose={() => setSelection(null)} />
      <RegistryMergePeopleDialog
        people={registry?.people ?? []}
        initialDuplicateId={mergePersonId}
        open={Boolean(mergePersonId)}
        onClose={() => setMergePersonId(null)}
        onPreview={(payload) => previewAdminRegistryPeopleMerge(payload)}
        onSubmit={(payload) => mutation.mutate(() => mergeAdminRegistryPeople(payload))}
      />
      <RegistryImportDialog
        busy={mutation.isPending || importMutation.isPending}
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onPreview={(payload) => previewAdminRegistryImport(payload)}
        onApply={(payload) => importMutation.mutateAsync(payload)}
      />
      <RegistryBindPersonDialog
        busy={mutation.isPending}
        people={registry?.people ?? []}
        state={bindDialog}
        onClose={() => setBindDialog(null)}
        onSubmit={(payload) => mutation.mutate(() => {
          if (payload.relationship_type === "shared_user") {
            return addAdminRegistrySharedUser({ device_id: payload.device_id, person_id: payload.person_id, reason: payload.reason });
          }
          if (payload.relationship_type === "responsible") {
            return assignAdminRegistryResponsible({ device_id: payload.device_id, person_id: payload.person_id, replace_existing: payload.replace_existing, reason: payload.reason });
          }
          return bindAdminRegistryDevicePerson(payload);
        })}
      />
      <RegistryTransferDeviceDialog
        busy={mutation.isPending}
        people={registry?.people ?? []}
        state={transferDialog}
        onClose={() => setTransferDialog(null)}
        onPreview={(payload) => previewAdminRegistryDeviceOwnerTransfer(payload)}
        onSubmit={(payload) => mutation.mutate(() => transferAdminRegistryDeviceOwner(payload))}
      />
      <RegistryIdentityDialog
        busy={mutation.isPending}
        state={identityDialog}
        onClose={() => setIdentityDialog(null)}
        onSubmit={(personId, payload) => mutation.mutate(() => createAdminRegistryPersonIdentity(personId, payload))}
      />
      <RegistryPersonEditDialog
        busy={mutation.isPending}
        state={personDialog}
        onClose={() => setPersonDialog(null)}
        onSubmit={(payload) => mutation.mutate(() => (
          payload.personId
            ? updateAdminRegistryPerson(payload.personId, payload)
            : createAdminRegistryPerson(payload)
        ))}
      />
    </section>
  );
}
