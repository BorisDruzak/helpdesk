import {
  Download,
  RefreshCcw,
  Search,
  ShieldCheck,
  Upload,
  UserPlus,
} from "lucide-react";

import { Button } from "../../../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../../../components/ui/card";
import { PageHeading } from "../../../components/ui/page-heading";
import { SearchField } from "../../../components/ui/search-field";
import {
  adminRegistryExportUrl,
  archiveAdminRegistryAudienceGroup,
  archiveAdminRegistryDepartment,
  archiveAdminRegistryLocation,
  approveAdminRegistrationClaim,
  completeAdminPasswordResetRequest,
  createAdminRegistryAudienceGroup,
  createAdminRegistryDepartment,
  createAdminRegistryLocation,
  mergeAdminRegistryDepartments,
  mergeAdminRegistryLocations,
  previewAdminRegistryAudienceGroupMembers,
  previewAdminRegistryDepartmentsMerge,
  previewAdminRegistryLocationsMerge,
  rejectAdminRegistrationClaim,
  revokeAdminDeviceUserBinding,
  updateAdminRegistryQualityIssue,
  setAdminRegistryAudienceGroupMembers,
  updateAdminRegistryDepartment,
  updateAdminRegistryLocation,
  updateAdminRegistryAudienceGroup,
  type AdminDeviceUserBinding,
  type AdminRegistrationClaim,
} from "../api";

import { RegistryAudienceGroupsTab } from "./registry-audience-groups-tab";
import { RegistryBindingsTab } from "./registry-bindings-tab";
import { RegistryBulkActions } from "./registry-bulk-actions";
import { RegistryDepartmentsTab } from "./registry-departments-tab";
import { RegistryDevicesTab } from "./registry-devices-tab";
import { RegistryLocationsTab } from "./registry-locations-tab";
import { RegistryOverviewTab } from "./registry-overview-tab";
import { RegistryPersonTools } from "./registry-person-tools";
import { RegistryPasswordResetRequestsTab } from "./registry-password-reset-requests-tab";
import { RegistryPoliciesTab } from "./registry-policies-tab";
import { RegistryProfileSchemaTab } from "./registry-profile-schema-tab";
import { RegistryQualityTab } from "./registry-quality-tab";
import { RegistryRequestsTab } from "./registry-requests-tab";
import { cn } from "../../../shared/ui/cn";

import { useRegistryWorkspace, type RegistryWorkspaceProps } from "./use-registry-workspace";
import { RegistryWorkspaceDialogs } from "./registry-workspace-dialogs";

export function RegistryWorkspace(props: RegistryWorkspaceProps) {
  const workspace = useRegistryWorkspace(props);
  const { personMode = false, personId = null } = props;
  const {
    visibleTabs, query, setQuery, tab, setTab,
    setSelection, setBindDialog, setTransferDialog, setIdentityDialog, setPersonDialog,
    setMergePersonId, setImportOpen, actionError, selectedDeviceIds, setSelectedDeviceIds,
    selectedPersonIds, setSelectedPersonIds, bulkResult, setBulkResult, selectedAudienceGroupId,
    setSelectedAudienceGroupId, audiencePreview, setAudiencePreview, registryQuery, accessSummaryQuery,
    mutation, bulkMutation, registry, visibleRegistry, pendingPasswordResetRequests,
    audienceGroups, audienceMembers, toggleSelected, toggleVisibleSelected, selectedBulkCount,
    bulkActions, clearCurrentBulkSelection, handleBulkAction, runWithReason, selectRecord,
    handleFixIssue, bindPersonToKnownDevice, linkUiUserToPerson, disableUiUser, archivePerson,
    exportType, activeTab,
  } = workspace;
  return (
    <section className="space-y-6">
      {!personMode ? <PageHeading
        actions={
          <>
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
        description="Устройства, привязки, заявки регистрации, качество данных и справочники. Учётные записи и права доступны в разделе «Пользователи»."
        eyebrow="Администрирование"
        title="Реестры"
      /> : null}

      <Card>
        <CardHeader className="gap-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <CardTitle>{personMode ? "Дополнительные инструменты" : "Операционный реестр"}</CardTitle>
            {personMode ? <div className="flex flex-wrap gap-2">
              <Button onClick={() => { window.location.href = adminRegistryExportUrl("people"); }} size="sm" variant="ghost">Экспорт людей</Button>
              <Button onClick={() => setImportOpen(true)} size="sm" variant="outline">Импорт людей</Button>
            </div> : null}
            {!personMode ? <div className="flex w-full min-w-0 items-center gap-2 xl:max-w-md">
              <Search className="h-4 w-4 text-slate-400" />
              <SearchField
                onChange={(event) => setQuery(event.target.value)}
                placeholder="ФИО, логин, почта, телефон, ID устройства, имя ПК, кабинет или ID привязки"
                value={query}
              />
            </div> : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {visibleTabs.map((item) => (
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

          {visibleRegistry && tab === "overview" ? <RegistryOverviewTab registry={visibleRegistry} onFixIssue={handleFixIssue} onSelect={selectRecord} /> : null}
          {visibleRegistry && tab === "devices" ? (
            <RegistryDevicesTab
              devices={visibleRegistry.assets}
              onBind={(deviceId) => setBindDialog({ deviceId, mode: "primary_user", title: "Привязать пользователя", replaceExisting: false })}
              onResponsible={(deviceId) => setBindDialog({ deviceId, mode: "responsible", title: "Назначить ответственного", replaceExisting: true })}
              onSelect={selectRecord}
              onShared={(deviceId) => setBindDialog({ deviceId, mode: "shared_user", title: "Добавить совместного пользователя", replaceExisting: false })}
              onToggleSelection={(deviceId) => toggleSelected(deviceId, setSelectedDeviceIds)}
              onToggleVisibleSelection={(deviceIds) => toggleVisibleSelected(deviceIds, setSelectedDeviceIds)}
              onTransfer={(device) => device.device_id && setTransferDialog({ deviceId: device.device_id, hostname: device.hostname })}
              selectedIds={selectedDeviceIds}
            />
          ) : null}
          {personMode && registry && tab === "people" ? <RegistryPersonTools
            person={registry.people.find(person => person.person_id === personId) ?? null}
            people={registry.people}
            uiUsers={registry.ui_users ?? []}
            bindings={registry.active_bindings}
            selectedIds={selectedPersonIds}
            onToggleSelection={id => toggleSelected(id, setSelectedPersonIds)}
            onIdentity={person => setIdentityDialog({ personId: person.person_id, personName: person.display_name })}
            onArchive={archivePerson}
            onBind={bindPersonToKnownDevice}
            onDisable={disableUiUser}
            onEdit={person => setPersonDialog({ person })}
            onLink={linkUiUserToPerson}
            onMerge={person => setMergePersonId(person.person_id)}
            onHistory={person => setSelection({ kind: "person", id: person.person_id })}
            onDevice={deviceId => setSelection({ kind: "device", id: deviceId })}
          /> : null}
          {visibleRegistry && tab === "bindings" ? (
            <RegistryBindingsTab
              bindings={visibleRegistry.bindings ?? visibleRegistry.active_bindings}
              onRevoke={(binding: AdminDeviceUserBinding) => runWithReason("Причина отзыва привязки", "Отозвано администратором", (reason) => revokeAdminDeviceUserBinding(binding.binding_id, reason))}
              onSelect={selectRecord}
              onTransferDevice={(deviceId) => setTransferDialog({ deviceId })}
            />
          ) : null}
          {visibleRegistry && tab === "requests" ? (
            <RegistryRequestsTab
              claims={visibleRegistry.registration_claims}
              registry={visibleRegistry}
              onApproveClaim={(claim: AdminRegistrationClaim, replaceExisting = false, override = false) => {
                if (override) {
                  runWithReason("Причина админского подтверждения", "Проверено администратором", (reason) => approveAdminRegistrationClaim(claim.claim_id, replaceExisting, true, reason));
                } else {
                  mutation.mutate(() => approveAdminRegistrationClaim(claim.claim_id, replaceExisting));
                }
              }}
              onRejectClaim={(claim) => runWithReason("Причина отклонения заявки", "Данные не подтверждены", (reason) => rejectAdminRegistrationClaim(claim.claim_id, reason))}
              onSelect={selectRecord}
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
          {visibleRegistry && tab === "quality" ? (
            <RegistryQualityTab
              issues={visibleRegistry.data_quality}
              onFix={handleFixIssue}
              onIgnore={(issue) => runWithReason(
                "Причина исключения проблемы качества",
                "Принято как контролируемое исключение реестра",
                (reason) => updateAdminRegistryQualityIssue({ issue_key: issue.issue_key, action: "ignore", reason }).then(() => undefined)
              )}
              onSelect={selectRecord}
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

      <RegistryWorkspaceDialogs workspace={workspace} personMode={personMode} />
    </section>
  );
}
