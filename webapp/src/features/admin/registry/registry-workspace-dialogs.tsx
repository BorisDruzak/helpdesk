import {
  addAdminRegistrySharedUser,
  assignAdminRegistryResponsible,
  bindAdminRegistryDevicePerson,
  createAdminRegistryPerson,
  createAdminRegistryPersonIdentity,
  linkAdminRegistryUiUserPerson,
  mergeAdminRegistryPeople,
  previewAdminRegistryBulk,
  previewAdminRegistryDeviceOwnerTransfer,
  previewAdminRegistryImport,
  previewAdminRegistryPeopleMerge,
  transferAdminRegistryDeviceOwner,
  updateAdminRegistryPerson,
} from "../api";

import { RegistryBindPersonDialog } from "./registry-bind-person-dialog";
import { RegistryBulkActionDialog } from "./registry-bulk-action-dialog";
import { RegistryDetailDrawer } from "./registry-detail-drawer";
import { RegistryIdentityDialog } from "./registry-identity-dialog";
import { RegistryImportDialog } from "./registry-import-dialog";
import { RegistryLinkUiUserDialog } from "./registry-link-ui-user-dialog";
import { RegistryMergePeopleDialog } from "./registry-merge-people-dialog";
import { RegistryPersonEditDialog } from "./registry-person-edit-dialog";
import { RegistryReasonDialog } from "./registry-reason-dialog";
import { RegistryTransferDeviceDialog } from "./registry-transfer-device-dialog";
import type { RegistryWorkspaceState } from "./use-registry-workspace";

export function RegistryWorkspaceDialogs({ workspace, personMode }: { workspace: RegistryWorkspaceState; personMode: boolean }) {
  const {
    selection, setSelection, bindDialog, setBindDialog, transferDialog,
    setTransferDialog, identityDialog, setIdentityDialog, personDialog, setPersonDialog,
    linkUiUserDialog, setLinkUiUserDialog, reasonDialog, setReasonDialog, bulkDialog,
    setBulkDialog, mergePersonId, setMergePersonId, importOpen, setImportOpen,
    mutation, bulkMutation, importMutation, registry, applyBulkAction,
  } = workspace;
  return <>
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
        scope={personMode ? "people" : "references"}
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
  </>;
}
