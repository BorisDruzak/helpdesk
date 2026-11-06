import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react";

import {
  applyAdminRegistryImport,
  adminRegistryExportUrl,
  archiveAdminRegistryPerson,
  bulkAssignAdminRegistryDeviceDepartment,
  bulkAssignAdminRegistryDeviceLocation,
  bulkAssignAdminRegistryPeopleDepartment,
  disableAdminRegistryUiUser,
  fetchAdminPasswordResetRequests,
  fetchAdminRegistry,
  fetchAdminRegistryAudienceGroupMembers,
  fetchAdminRegistryAudienceGroups,
  revokeAdminDeviceUserBinding,
  type AdminRegistryAudiencePreview,
  type AdminRegistryBulkResponse,
  type AdminRegistryPayload,
} from "../api";
import { fetchAccessSummary } from "../../access-control/api";

import type { BindPersonDialogState } from "./registry-bind-person-dialog";
import type { RegistryBulkDialogState, RegistryBulkOperation } from "./registry-bulk-action-dialog";
import type { RegistryBulkAction } from "./registry-bulk-actions";
import type { IdentityDialogState } from "./registry-identity-dialog";
import type { LinkUiUserDialogState } from "./registry-link-ui-user-dialog";
import type { PersonEditDialogState } from "./registry-person-edit-dialog";
import type { RegistryReasonDialogState } from "./registry-reason-dialog";
import { filterRegistryPayload, type RegistrySelection, type RegistryTabKey } from "./registry-utils";
import { registryTabs, personTabs } from "./registry-workspace-tabs";

export type RegistryWorkspaceProps = {
  personMode?: boolean;
  personId?: string | null;
  initialTab?: string | null;
  onOpenPerson?: (personId: string) => void;
  onOpenAccount?: (login: string) => void;
};

function registryActionErrorMessage(error: unknown, fallback: string): string {
  const message = error instanceof Error ? error.message : fallback;
  if (message.includes("user confirmation required before approval")) {
    return "Нужно подтверждение пользователя на агенте. Для ручного обхода используйте «Админское подтверждение» с причиной.";
  }
  return message;
}

export function useRegistryWorkspace({ personMode = false, initialTab, onOpenPerson, onOpenAccount }: RegistryWorkspaceProps) {
  const visibleTabs = personMode ? personTabs : registryTabs;
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<RegistryTabKey>(visibleTabs.find(item => item.key === initialTab)?.key ?? (personMode ? "people" : "overview"));
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
  const [bulkResult, setBulkResult] = useState<AdminRegistryBulkResponse | null>(null);
  const [selectedAudienceGroupId, setSelectedAudienceGroupId] = useState<string | null>(null);
  const [audiencePreview, setAudiencePreview] = useState<AdminRegistryAudiencePreview | null>(null);

  const registryQuery = useQuery({
    queryKey: ["admin-registry"],
    queryFn: fetchAdminRegistry,
    retry: false,
    refetchInterval: 15_000,
  });
  const passwordResetRequestsQuery = useQuery({
    queryKey: ["admin-registry-password-reset-requests"],
    enabled: personMode && tab === "password_reset",
    queryFn: () => fetchAdminPasswordResetRequests("pending"),
    retry: false,
    refetchInterval: 15_000,
  });
  const audienceGroupsQuery = useQuery({
    queryKey: ["admin-registry-audience-groups"],
    enabled: !personMode,
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
    await Promise.all([
      "admin-registry", "admin-registry-account-login-requests",
      "admin-registry-password-reset-requests", "admin-registry-audience-groups",
      "admin-registry-audience-group-members", "admin-user-accounts",
      "admin-access-summary", "admin-access-effective", "admin-access-audit",
    ].map(key => queryClient.invalidateQueries({ queryKey: [key] })));
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
    0;
  const bulkActions: RegistryBulkAction[] = useMemo(() => {
    if (tab === "devices") {
      return [
        { key: "devices.assign_location", label: "Назначить локацию" },
        { key: "devices.assign_department", label: "Назначить подразделение" },
      ];
    }
    if (tab === "people") {
      return [{ key: "people.assign_department", label: "Назначить подразделение" }];
    }
    return [];
  }, [tab]);
  const clearCurrentBulkSelection = () => {
    if (tab === "devices") {
      setSelectedDeviceIds([]);
    } else if (tab === "people") {
      setSelectedPersonIds([]);
    }
  };

  const handleBulkAction = (operation: string) => {
    const typedOperation = operation as RegistryBulkOperation;
    const ids =
      typedOperation.startsWith("devices.") ? selectedDeviceIds :
      typedOperation.startsWith("people.") ? selectedPersonIds :
      [];
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
      if (state.operation === "people.assign_department") {
        return bulkAssignAdminRegistryPeopleDepartment({ ids: state.ids, department_id: payload.target_id ?? "", reason: payload.reason });
      }
      return bulkAssignAdminRegistryPeopleDepartment({ ids: state.ids, department_id: payload.target_id ?? "", reason: payload.reason });
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

  const selectRecord = (next: RegistrySelection) => {
    if (!personMode && next?.kind === "person" && onOpenPerson) {
      onOpenPerson(next.id);
      return;
    }
    setSelection(next);
  };

  const handleFixIssue = (issue: AdminRegistryPayload["data_quality"][number]) => {
    if (!personMode && issue.kind === "ui_user_unlinked_registry_person" && onOpenAccount) {
      onOpenAccount(issue.object_id);
      return;
    }
    if (!personMode && issue.person_id && ["missing_identity", "duplicate_person", "ui_user_unlinked_registry_person"].includes(issue.kind) && onOpenPerson) {
      onOpenPerson(issue.person_id);
      return;
    }
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

  const exportType: Parameters<typeof adminRegistryExportUrl>[0] =
    tab === "people" ? "people" :
    tab === "bindings" ? "bindings" :
    tab === "locations" ? "locations" :
    tab === "departments" ? "departments" :
    tab === "audience_groups" ? "audience_groups" :
    tab === "quality" ? "quality" :
    "devices";
  const activeTab = visibleTabs.find((item) => item.key === tab) ?? visibleTabs[0];

  return {
    visibleTabs, query, setQuery, tab, setTab,
    selection, setSelection, bindDialog, setBindDialog, transferDialog,
    setTransferDialog, identityDialog, setIdentityDialog, personDialog, setPersonDialog,
    linkUiUserDialog, setLinkUiUserDialog, reasonDialog, setReasonDialog, bulkDialog,
    setBulkDialog, mergePersonId, setMergePersonId, importOpen, setImportOpen,
    actionError, selectedDeviceIds, setSelectedDeviceIds, selectedPersonIds, setSelectedPersonIds,
    bulkResult, setBulkResult, selectedAudienceGroupId, setSelectedAudienceGroupId, audiencePreview,
    setAudiencePreview, registryQuery, accessSummaryQuery, mutation, bulkMutation,
    importMutation, registry, visibleRegistry, pendingPasswordResetRequests, audienceGroups,
    audienceMembers, toggleSelected, toggleVisibleSelected, selectedBulkCount, bulkActions,
    clearCurrentBulkSelection, handleBulkAction, applyBulkAction, runWithReason, selectRecord,
    handleFixIssue, bindPersonToKnownDevice, linkUiUserToPerson, disableUiUser, archivePerson,
    exportType, activeTab,
  };
}

export type RegistryWorkspaceState = ReturnType<typeof useRegistryWorkspace>;
