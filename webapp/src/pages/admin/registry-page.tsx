import { Download, Plus, RefreshCcw, Search, ShieldCheck, Upload, UserPlus } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type Dispatch, type SetStateAction } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import {
  addAdminRegistrySharedUser,
  adminRegistryExportUrl,
  applyAdminRegistryImport,
  archiveAdminRegistryAudienceGroup,
  archiveAdminRegistryDepartment,
  archiveAdminRegistryLocation,
  archiveAdminRegistryPerson,
  approveAdminAccountLoginRequest,
  approveAdminRegistrationClaim,
  assignAdminRegistryResponsible,
  bindAdminRegistryDevicePerson,
  bulkAssignAdminRegistryDeviceDepartment,
  bulkAssignAdminRegistryDeviceLocation,
  bulkAssignAdminRegistryPeopleDepartment,
  bulkRevokeAdminRegistryAccountSessions,
  bulkRevokeAdminRegistryDeviceAccountSessions,
  completeAdminPasswordResetRequest,
  createAdminRegistryAudienceGroup,
  createAdminRegistryDepartment,
  createAdminRegistryLocation,
  createAdminRegistryPerson,
  createAdminRegistryPersonIdentity,
  disableAdminRegistryUiUser,
  fetchAdminAccountLoginRequests,
  fetchAdminPasswordResetRequests,
  fetchAdminRegistry,
  fetchAdminRegistryAudienceGroupMembers,
  fetchAdminRegistryAudienceGroups,
  linkAdminRegistryUiUserPerson,
  mergeAdminRegistryDepartments,
  mergeAdminRegistryLocations,
  mergeAdminRegistryPeople,
  previewAdminRegistryAudienceGroupMembers,
  previewAdminRegistryBulk,
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
  setAdminRegistryAudienceGroupMembers,
  updateAdminRegistryDepartment,
  updateAdminRegistryLocation,
  updateAdminRegistryAudienceGroup,
  updateAdminRegistryPerson,
  type AdminDeviceAccountSession,
  type AdminDeviceUserBinding,
  type AdminRegistrationClaim,
  type AdminRegistryAudiencePreview,
  type AdminRegistryBulkResponse,
  type AdminRegistryPayload,
} from "../../features/admin/api";
import { fetchAccessSummary } from "../../features/access-control/api";
import { RegistryAccountSessionsTab } from "../../features/admin/registry/registry-account-sessions-tab";
import { RegistryAccessGroupsTab } from "../../features/admin/registry/registry-access-groups-tab";
import { RegistryAudienceGroupsTab } from "../../features/admin/registry/registry-audience-groups-tab";
import { RegistryBindPersonDialog, type BindPersonDialogState } from "../../features/admin/registry/registry-bind-person-dialog";
import { RegistryBindingsTab } from "../../features/admin/registry/registry-bindings-tab";
import { RegistryBulkActionDialog, type RegistryBulkDialogState, type RegistryBulkOperation } from "../../features/admin/registry/registry-bulk-action-dialog";
import { RegistryBulkActions, type RegistryBulkAction } from "../../features/admin/registry/registry-bulk-actions";
import { RegistryDepartmentsTab } from "../../features/admin/registry/registry-departments-tab";
import { RegistryDetailDrawer } from "../../features/admin/registry/registry-detail-drawer";
import { RegistryDevicesTab } from "../../features/admin/registry/registry-devices-tab";
import { RegistryIdentityDialog, type IdentityDialogState } from "../../features/admin/registry/registry-identity-dialog";
import { RegistryImportDialog } from "../../features/admin/registry/registry-import-dialog";
import { RegistryLinkUiUserDialog, type LinkUiUserDialogState } from "../../features/admin/registry/registry-link-ui-user-dialog";
import { RegistryLocationsTab } from "../../features/admin/registry/registry-locations-tab";
import { RegistryMergePeopleDialog } from "../../features/admin/registry/registry-merge-people-dialog";
import { RegistryOverviewTab } from "../../features/admin/registry/registry-overview-tab";
import { RegistryPeopleTab } from "../../features/admin/registry/registry-people-tab";
import { RegistryPersonEditDialog, type PersonEditDialogState } from "../../features/admin/registry/registry-person-edit-dialog";
import { RegistryPasswordResetRequestsTab } from "../../features/admin/registry/registry-password-reset-requests-tab";
import { RegistryPoliciesTab } from "../../features/admin/registry/registry-policies-tab";
import { RegistryProfileSchemaTab } from "../../features/admin/registry/registry-profile-schema-tab";
import { RegistryQualityTab } from "../../features/admin/registry/registry-quality-tab";
import { RegistryReasonDialog, type RegistryReasonDialogState } from "../../features/admin/registry/registry-reason-dialog";
import { RegistryRequestsTab } from "../../features/admin/registry/registry-requests-tab";
import { RegistryTransferDeviceDialog } from "../../features/admin/registry/registry-transfer-device-dialog";
import { filterRegistryPayload, type RegistrySelection, type RegistryTabKey } from "../../features/admin/registry/registry-utils";
import { cn } from "../../shared/ui/cn";

const tabs: Array<{ key: RegistryTabKey; label: string; description: string; p1?: boolean }> = [
  { key: "overview", label: "Обзор", description: "Сводка по устройствам, людям, заявкам и проблемам качества. Начинайте отсюда, если не ясно, где исправлять данные." },
  { key: "devices", label: "Устройства", description: "Работа с ПК и агентами: открыть карточку, привязать владельца, передать устройство, добавить совместного пользователя или отозвать сессии." },
  { key: "people", label: "Пользователи", description: "Карточки людей, UI-аккаунты, идентичности и операции слияния. Технические идентификаторы оставлены только для точной диагностики." },
  { key: "bindings", label: "Привязки", description: "Активные и исторические связи устройство-пользователь. Фильтры показывают тип связи или состояние." },
  { key: "requests", label: "Заявки", description: "Заявки регистрации и входа в другой аккаунт. Перед подтверждением проверяйте дифф: устройство, текущая привязка, заявленные ФИО, подразделение и локация." },
  { key: "password_reset", label: "Смена пароля", description: "Заявки пользователей на смену забытого UI-пароля. Закрытие заявки сразу устанавливает новый пароль и фиксирует причину." },
  { key: "account_sessions", label: "Аккаунт-сессии", description: "Серверные сессии пользователей на устройствах. Отзыв сессии прекращает выбранный контекст аккаунта на агенте." },
  { key: "quality", label: "Качество данных", description: "Действительные проблемы качества и подсказки по исправлению. Игнорирование и отсрочка требуют причины для аудита." },
  { key: "locations", label: "Локации", description: "Справочник зданий, этажей и кабинетов. Архивация и слияние требуют причины и предварительного просмотра.", p1: true },
  { key: "departments", label: "Подразделения", description: "Организационная структура для людей, устройств и правил видимости. Слияние подразделений выполняйте только после предпросмотра.", p1: true },
  { key: "access_groups", label: "Группы доступа", description: "Только сводка RBAC-групп. Права и очереди редактируются в отдельном RBAC-редакторе.", p1: true },
  { key: "audience_groups", label: "Аудитории", description: "Группы таргетинга для базы знаний и сервисов. Аудитории не выдают права доступа, а только участвуют в правилах видимости.", p1: true },
  { key: "profile_schema", label: "Схема профиля", description: "Управляемые поля профиля заявителя. Системные поля нельзя удалить, пользовательские поля пишутся только в контролируемый блок.", p1: true },
  { key: "policies", label: "Политики", description: "Правила регистрации, аккаунт-сессий и видимости тикетов. Перед сохранением используйте предпросмотр.", p1: true },
];

function PlaceholderTab({ title }: { title: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-sm text-slate-500">
          P1: базовое чтение уже доступно в данных страницы; редактирование, слияние дублей и редактор политик добавляются отдельными безопасными проходами.
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
  const [linkUiUserDialog, setLinkUiUserDialog] = useState<LinkUiUserDialogState>(null);
  const [reasonDialog, setReasonDialog] = useState<RegistryReasonDialogState>(null);
  const [bulkDialog, setBulkDialog] = useState<RegistryBulkDialogState>(null);
  const [mergePersonId, setMergePersonId] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [selectedDeviceIds, setSelectedDeviceIds] = useState<string[]>([]);
  const [selectedPersonIds, setSelectedPersonIds] = useState<string[]>([]);
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);
  const [bulkResult, setBulkResult] = useState<AdminRegistryBulkResponse | null>(null);
  const [selectedAudienceGroupId, setSelectedAudienceGroupId] = useState<string | null>(null);
  const [audiencePreview, setAudiencePreview] = useState<AdminRegistryAudiencePreview | null>(null);

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
  const passwordResetRequestsQuery = useQuery({
    queryKey: ["admin-registry-password-reset-requests"],
    queryFn: () => fetchAdminPasswordResetRequests("pending"),
    retry: false,
    refetchInterval: 15_000,
  });
  const audienceGroupsQuery = useQuery({
    queryKey: ["admin-registry-audience-groups"],
    queryFn: () => fetchAdminRegistryAudienceGroups(false),
    retry: false,
    refetchInterval: 30_000,
  });
  const audienceMembersQuery = useQuery({
    queryKey: ["admin-registry-audience-group-members", selectedAudienceGroupId],
    queryFn: () => fetchAdminRegistryAudienceGroupMembers(selectedAudienceGroupId ?? ""),
    enabled: Boolean(selectedAudienceGroupId),
    retry: false,
  });
  const accessSummaryQuery = useQuery({
    queryKey: ["admin-access-summary"],
    queryFn: fetchAccessSummary,
    enabled: tab === "audience_groups",
    retry: false,
  });

  const invalidateRegistry = async () => {
    await queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-registry-account-login-requests"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-registry-password-reset-requests"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-registry-audience-groups"] });
    await queryClient.invalidateQueries({ queryKey: ["admin-registry-audience-group-members"] });
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
      setLinkUiUserDialog(null);
      setReasonDialog(null);
      setMergePersonId(null);
      setImportOpen(false);
      await invalidateRegistry();
    },
  });

  const bulkMutation = useMutation({
    mutationFn: async (operation: () => Promise<AdminRegistryBulkResponse>) => operation(),
    onError: (error) => setActionError(registryActionErrorMessage(error, "Не удалось выполнить массовую операцию")),
    onSuccess: async (result) => {
      setActionError(null);
      setBulkResult(result);
      setBulkDialog(null);
      await invalidateRegistry();
    },
  });

  const importMutation = useMutation({
    mutationFn: applyAdminRegistryImport,
    onError: (error) => setActionError(registryActionErrorMessage(error, "Не удалось применить импорт")),
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
  const pendingPasswordResetRequests = passwordResetRequestsQuery.data?.items ?? registry?.password_reset_requests ?? [];
  const audienceGroups = audienceGroupsQuery.data?.groups ?? [];
  const audienceMembers = audienceMembersQuery.data?.members ?? [];

  useEffect(() => {
    if (!selectedAudienceGroupId && audienceGroups.length) {
      setSelectedAudienceGroupId(audienceGroups[0].audience_group_id);
    }
  }, [audienceGroups, selectedAudienceGroupId]);

  useEffect(() => {
    setAudiencePreview(null);
  }, [selectedAudienceGroupId]);

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
        { key: "devices.assign_location", label: "Назначить локацию" },
        { key: "devices.assign_department", label: "Назначить подразделение" },
        { key: "devices.revoke_account_sessions", label: "Отозвать сессии" },
      ];
    }
    if (tab === "people") {
      return [{ key: "people.assign_department", label: "Назначить подразделение" }];
    }
    if (tab === "account_sessions") {
      return [{ key: "account_sessions.revoke", label: "Отозвать сессии" }];
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
    const typedOperation = operation as RegistryBulkOperation;
    const ids =
      typedOperation.startsWith("devices.") ? selectedDeviceIds :
      typedOperation.startsWith("people.") ? selectedPersonIds :
      selectedSessionIds;
    if (!ids.length) {
      return;
    }
    setBulkDialog({ operation: typedOperation, ids });
  };

  const applyBulkAction = async (state: Exclude<RegistryBulkDialogState, null>, payload: { target_id?: string; reason: string }) => {
    return bulkMutation.mutateAsync(() => {
      if (state.operation === "devices.assign_location") {
        return bulkAssignAdminRegistryDeviceLocation({ ids: state.ids, location_id: payload.target_id ?? "", reason: payload.reason });
      }
      if (state.operation === "devices.assign_department") {
        return bulkAssignAdminRegistryDeviceDepartment({ ids: state.ids, department_id: payload.target_id ?? "", reason: payload.reason });
      }
      if (state.operation === "devices.revoke_account_sessions") {
        return bulkRevokeAdminRegistryDeviceAccountSessions(state.ids, payload.reason);
      }
      if (state.operation === "people.assign_department") {
        return bulkAssignAdminRegistryPeopleDepartment({ ids: state.ids, department_id: payload.target_id ?? "", reason: payload.reason });
      }
      return bulkRevokeAdminRegistryAccountSessions(state.ids, payload.reason);
    });
  };

  const runWithReason = (label: string, fallback: string, action: (reason: string) => Promise<void>, tone: "default" | "danger" = "default") => {
    setReasonDialog({
      title: label,
      defaultReason: fallback,
      tone,
      onConfirm: (reason) => mutation.mutate(() => action(reason)),
    });
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
        runWithReason("Причина отзыва устаревшей привязки", "Устаревшая привязка", (reason) => revokeAdminDeviceUserBinding(binding.binding_id, reason));
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
    runWithReason("Причина отзыва аккаунт-сессий", "Администратор отозвал сессии устройства", async (reason) => {
      await Promise.all(sessions.map((session) => revokeAdminDeviceAccountSession(session.session_id, reason)));
    });
  };

  const bindPersonToKnownDevice = (person: AdminRegistryPayload["people"][number]) => {
    setBindDialog({ deviceId: "", personId: person.person_id, mode: "primary_user", title: `Привязать ${person.display_name} к устройству`, replaceExisting: false });
  };

  const linkUiUserToPerson = (person: AdminRegistryPayload["people"][number]) => {
    setLinkUiUserDialog({ person });
  };

  const disableUiUser = (uiUser: NonNullable<AdminRegistryPayload["ui_users"]>[number]) => {
    runWithReason(
      "Причина отключения входа",
      "UI аккаунт больше не должен иметь доступ",
      (reason) => disableAdminRegistryUiUser(uiUser.user_login, reason),
      "danger",
    );
  };

  const archivePerson = (person: AdminRegistryPayload["people"][number]) => {
    runWithReason(
      "Причина архивации пользователя",
      "Пользователь больше не работает с системой",
      (reason) => archiveAdminRegistryPerson(person.person_id, reason),
      "danger",
    );
  };

  const exportType =
    tab === "people" ? "people" :
    tab === "bindings" ? "bindings" :
    tab === "account_sessions" ? "sessions" :
    tab === "locations" ? "locations" :
    tab === "departments" ? "departments" :
    tab === "audience_groups" ? "audience_groups" :
    tab === "quality" ? "quality" :
    "devices";
  const activeTab = tabs.find((item) => item.key === tab) ?? tabs[0];

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <Button leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setPersonDialog({})} size="sm" title="Создать карточку пользователя в реестре" variant="outline">
              Пользователь
            </Button>
            <Button leadingIcon={<UserPlus className="h-4 w-4" />} onClick={() => setBindDialog({ deviceId: "", mode: "primary_user", title: "Привязать устройство", replaceExisting: false })} size="sm" title="Привязать устройство к основному пользователю" variant="outline">
              Привязать устройство
            </Button>
            <Button leadingIcon={<ShieldCheck className="h-4 w-4" />} onClick={() => setTab("quality")} size="sm" title="Открыть проблемы качества и рекомендации по исправлению" variant="outline">
              Проверка качества
            </Button>
            <Button leadingIcon={<Download className="h-4 w-4" />} onClick={() => { window.location.href = adminRegistryExportUrl(exportType); }} size="sm" title={`Экспортировать текущий раздел: ${activeTab.label}`} variant="ghost">
              Экспорт
            </Button>
            <Button leadingIcon={<Upload className="h-4 w-4" />} onClick={() => setImportOpen(true)} size="sm" title="Открыть безопасный CSV-импорт с предпросмотром" variant="ghost">
              Импорт
            </Button>
            <Button leadingIcon={<RefreshCcw className="h-4 w-4" />} onClick={() => void registryQuery.refetch()} size="sm" title="Обновить данные реестра с сервера">
              Обновить
            </Button>
          </>
        }
        description="Единое рабочее место администратора для устройств, пользователей, привязок, аккаунт-сессий, заявок регистрации, аудиторий и качества данных."
        eyebrow="Администрирование"
        title="Центр регистрации и привязок"
      />

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <CardTitle>Операционный реестр</CardTitle>
            <div className="flex min-w-[320px] items-center gap-2">
              <Search className="h-4 w-4 text-slate-400" />
              <SearchField
                onChange={(event) => setQuery(event.target.value)}
                placeholder="ФИО, логин, почта, телефон, ID устройства, имя ПК, кабинет, ID привязки или сессии"
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
                title={item.description}
                type="button"
              >
                {item.label}{item.p1 ? " · P1" : ""}
              </button>
            ))}
          </div>
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-600">
            {activeTab.description}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? <p className="text-sm text-rose-600">{actionError}</p> : null}
          {registryQuery.isLoading ? <p className="text-sm text-slate-500">Загружаем центр управления реестром...</p> : null}
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
              onShared={(deviceId) => setBindDialog({ deviceId, mode: "shared_user", title: "Добавить совместного пользователя", replaceExisting: false })}
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
              onArchive={archivePerson}
              onBindToDevice={bindPersonToKnownDevice}
              onDisableUiUser={disableUiUser}
              onEdit={(person) => setPersonDialog({ person })}
              onLinkUiUser={linkUiUserToPerson}
              onMerge={(person) => setMergePersonId(person.person_id)}
              onSelect={setSelection}
              onToggleSelection={(personId) => toggleSelected(personId, setSelectedPersonIds)}
              onToggleVisibleSelection={(personIds) => toggleVisibleSelected(personIds, setSelectedPersonIds)}
              selectedIds={selectedPersonIds}
              uiUsers={visibleRegistry.ui_users ?? []}
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
              registry={visibleRegistry}
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
          {tab === "password_reset" ? (
            <RegistryPasswordResetRequestsTab
              busy={mutation.isPending}
              requests={pendingPasswordResetRequests}
              onComplete={(request, payload) => mutation.mutate(() => (
                completeAdminPasswordResetRequest(request.request_id, payload).then(() => undefined)
              ))}
            />
          ) : null}
          {visibleRegistry && tab === "account_sessions" ? (
            <RegistryAccountSessionsTab
              sessions={visibleRegistry.account_sessions ?? []}
              onRevoke={(session: AdminDeviceAccountSession) => runWithReason("Причина отзыва аккаунт-сессии", "Отозвано администратором", (reason) => revokeAdminDeviceAccountSession(session.session_id, reason))}
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
              onIgnore={(issue) => runWithReason(
                "Причина исключения проблемы качества",
                "Принято как контролируемое исключение реестра",
                (reason) => updateAdminRegistryQualityIssue({ issue_key: issue.issue_key, action: "ignore", reason }).then(() => undefined)
              )}
              onSelect={setSelection}
              onSnooze={(issue, days) => runWithReason(
                "Причина откладывания проблемы качества",
                "Проблема отложена для планового исправления",
                (reason) => updateAdminRegistryQualityIssue({ issue_key: issue.issue_key, action: "snooze", reason, days }).then(() => undefined)
              )}
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
          {tab === "access_groups" ? <RegistryAccessGroupsTab /> : null}
          {visibleRegistry && tab === "audience_groups" ? (
            <RegistryAudienceGroupsTab
              accessGroups={accessSummaryQuery.data?.access_groups ?? []}
              busy={mutation.isPending}
              groups={audienceGroups}
              members={audienceMembers}
              preview={audiencePreview}
              registry={visibleRegistry}
              selectedGroupId={selectedAudienceGroupId}
              onArchive={(group, reason) => mutation.mutate(() => archiveAdminRegistryAudienceGroup(group.audience_group_id, reason).then(() => undefined))}
              onCreate={(payload) => mutation.mutate(() => createAdminRegistryAudienceGroup(payload).then((result) => {
                setSelectedAudienceGroupId(result.group.audience_group_id);
              }))}
              onPreviewMembers={async (groupId, members) => {
                const result = await previewAdminRegistryAudienceGroupMembers(groupId, members);
                setAudiencePreview(result.preview);
              }}
              onSaveMembers={(groupId, members, reason) => mutation.mutate(() => setAdminRegistryAudienceGroupMembers(groupId, { members, reason }).then(() => undefined))}
              onSelectGroup={(groupId) => setSelectedAudienceGroupId(groupId)}
              onUpdate={(groupId, payload) => mutation.mutate(() => updateAdminRegistryAudienceGroup(groupId, payload).then(() => undefined))}
            />
          ) : null}
          {tab === "profile_schema" ? <RegistryProfileSchemaTab /> : null}
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
      <RegistryBulkActionDialog
        busy={bulkMutation.isPending}
        registry={registry}
        state={bulkDialog}
        onApply={applyBulkAction}
        onClose={() => setBulkDialog(null)}
        onPreview={(payload) => previewAdminRegistryBulk(payload)}
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
      <RegistryLinkUiUserDialog
        busy={mutation.isPending}
        state={linkUiUserDialog}
        uiUsers={registry?.ui_users ?? []}
        onClose={() => setLinkUiUserDialog(null)}
        onSubmit={(payload) => mutation.mutate(() => linkAdminRegistryUiUserPerson(payload.user_login, { person_id: payload.person_id, reason: payload.reason }))}
      />
      <RegistryReasonDialog
        busy={mutation.isPending}
        state={reasonDialog}
        onClose={() => setReasonDialog(null)}
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
