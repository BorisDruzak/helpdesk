import { Check, X } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminAccountLoginRequest, AdminDeviceUserBinding, AdminRegistrationClaim, AdminRegistryPayload } from "../api";
import { formatDateTime, registryStatusLabel, relationshipTypeLabel, statusTone, type RegistrySelection } from "./registry-utils";

type RegistryApprovalContext = Pick<AdminRegistryPayload, "assets" | "people" | "locations" | "departments" | "active_bindings" | "bindings">;

type Props = {
  claims: AdminRegistrationClaim[];
  loginRequests: AdminAccountLoginRequest[];
  registry: RegistryApprovalContext;
  onApproveClaim: (claim: AdminRegistrationClaim, replaceExisting?: boolean, override?: boolean) => void;
  onRejectClaim: (claim: AdminRegistrationClaim) => void;
  onApproveLoginRequest: (request: AdminAccountLoginRequest) => void;
  onRejectLoginRequest: (request: AdminAccountLoginRequest) => void;
  onSelect: (selection: RegistrySelection) => void;
};

function textValue(value: unknown): string | null {
  const text = String(value ?? "").trim();
  return text || null;
}

function accountName(request: AdminAccountLoginRequest): string {
  return String(request.requested_account.display_name ?? request.requested_account.full_name ?? request.requested_account.login ?? "Аккаунт не указан");
}

const terminalClaimStatuses = new Set(["approved", "rejected", "superseded", "expired"]);

export function canApproveClaim(claim: AdminRegistrationClaim): boolean {
  return !terminalClaimStatuses.has(claim.status) && (claim.status === "user_confirmed" || claim.status === "pending_admin_review" || Boolean(claim.user_confirmed_at));
}

export function claimActionHint(claim: AdminRegistrationClaim): string | null {
  if (claim.status === "pending_user_confirmation" || claim.status === "self_reported") {
    return "Ожидается подтверждение пользователя на агенте. Для ручного обхода используйте админское подтверждение.";
  }
  if (claim.status === "conflict" && !claim.user_confirmed_at) {
    return "Конфликт без пользовательского подтверждения: используйте админское подтверждение с заменой.";
  }
  if (terminalClaimStatuses.has(claim.status)) {
    return "Заявка уже завершена.";
  }
  return null;
}

function findCurrentBinding(claim: AdminRegistrationClaim, registry: RegistryApprovalContext): AdminDeviceUserBinding | null {
  const bindings = registry.bindings ?? registry.active_bindings;
  return bindings.find((binding) => (
    binding.device_id === claim.device_id
    && binding.status === "active"
    && binding.relationship_type === "primary_user"
  )) ?? bindings.find((binding) => binding.device_id === claim.device_id && binding.status === "active") ?? null;
}

function labelDepartment(registry: RegistryApprovalContext, departmentId: string | null): string {
  if (!departmentId) return "не указано";
  const department = registry.departments.find((item) => (item.department_id ?? item.id) === departmentId);
  return department?.name ?? departmentId;
}

function labelLocation(registry: RegistryApprovalContext, locationId: string | null): string {
  if (!locationId) return "не указано";
  const location = registry.locations.find((item) => (item.location_id ?? item.id) === locationId);
  return location?.display_name ?? locationId;
}

function conflictReasonLabel(reason?: string | null): string {
  const labels: Record<string, string> = {
    active_primary_user_exists: "уже есть активный основной пользователь",
    device_not_found: "устройство не найдено",
    person_not_found: "пользователь не найден",
  };
  return labels[reason || ""] || "требуется проверка администратора";
}

function ApprovalDiff({ claim, registry }: { claim: AdminRegistrationClaim; registry: RegistryApprovalContext }) {
  const profile = claim.profile_snapshot;
  const currentBinding = findCurrentBinding(claim, registry);
  const asset = registry.assets.find((item) => item.device_id === claim.device_id || item.id === claim.asset_id) ?? null;
  const claimedName = textValue(profile.full_name) ?? textValue(profile.display_name) ?? claim.person_name ?? "не указано";
  const claimedDepartmentId = textValue(profile.department_id);
  const claimedLocationId = textValue(profile.location_id);
  const identity = [textValue(profile.email), textValue(profile.login)].filter(Boolean).join(" / ") || "не указано";
  const deviceLabel = textValue(profile.hostname) ?? asset?.hostname ?? claim.device_id;
  const currentBindingLabel = currentBinding
    ? `${currentBinding.person_name ?? currentBinding.person_id} · ${relationshipTypeLabel(currentBinding.relationship_type)}`
    : "нет активной привязки";

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
      <p className="font-semibold text-amber-950">Дифф подтверждения</p>
      <p>Устройство: {deviceLabel}</p>
      <p>Текущая привязка: {currentBindingLabel}</p>
      <p>Заявлено: {claimedName}</p>
      <p>Подразделение: {labelDepartment(registry, claimedDepartmentId)}</p>
      <p>Локация: {labelLocation(registry, claimedLocationId)}</p>
      <p>Идентичность: {identity}</p>
      <p>Тип привязки: {relationshipTypeLabel(claim.relationship_type)}</p>
      {claim.conflict_reason ? <p>Блокер: {conflictReasonLabel(claim.conflict_reason)}</p> : null}
    </div>
  );
}

export function RegistryRequestsTab({ claims, loginRequests, registry, onApproveClaim, onApproveLoginRequest, onRejectClaim, onRejectLoginRequest, onSelect }: Props) {
  return (
    <div className="space-y-5">
      <section className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[1140px] grid-cols-[190px_190px_190px_150px_150px_120px_340px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>ПК</span><span>ID устройства</span><span>Пользователь</span><span>Тип</span><span>Статус</span><span>Подана</span><span>Действия</span>
        </div>
        {claims.length ? claims.map((claim) => {
          const canApprove = canApproveClaim(claim);
          const isTerminal = terminalClaimStatuses.has(claim.status);
          const isConflict = claim.status === "conflict";
          const hint = claimActionHint(claim);
          return (
            <div className="grid min-w-[1140px] grid-cols-[190px_190px_190px_150px_150px_120px_340px] gap-3 border-t border-border px-4 py-3 text-sm" key={claim.claim_id}>
              <button className="text-left font-semibold text-brand-700" onClick={() => onSelect({ kind: "claim", id: claim.claim_id })} type="button">{String(claim.profile_snapshot.hostname ?? "ПК")}</button>
              <span className="break-all">{claim.device_id}</span>
              <span>{claim.person_name ?? String(claim.profile_snapshot.display_name ?? claim.profile_snapshot.login ?? "Не определен")}</span>
              <span title={claim.relationship_type}>{relationshipTypeLabel(claim.relationship_type)}</span>
              <Badge tone={statusTone(claim.status)}>{registryStatusLabel(claim.status)}</Badge>
              <span>{formatDateTime(claim.submitted_at)}</span>
              <div className="space-y-1">
                <ApprovalDiff claim={claim} registry={registry} />
                <div className="flex flex-wrap gap-2">
                  <Button disabled={!canApprove} leadingIcon={<Check className="h-4 w-4" />} onClick={() => onApproveClaim(claim)} size="sm" title={!canApprove ? "Нужно подтверждение пользователя или админский обход с причиной" : "Подтвердить заявку без замены активной привязки"} variant="outline">Подтвердить</Button>
                  <Button disabled={!isConflict || (!canApprove && !claim.user_confirmed_at)} onClick={() => onApproveClaim(claim, true)} size="sm" title="Подтвердить заявку и заменить текущую активную привязку" variant="outline">С заменой</Button>
                  <Button disabled={isTerminal} onClick={() => onApproveClaim(claim, isConflict, true)} size="sm" title="Администратор подтверждает вручную; причина обязательна и попадет в аудит" variant="ghost">{isConflict ? "Админ с заменой" : "Админское подтверждение"}</Button>
                  <Button disabled={isTerminal} leadingIcon={<X className="h-4 w-4" />} onClick={() => onRejectClaim(claim)} size="sm" title="Отклонить заявку с обязательной причиной" variant="ghost">Отклонить</Button>
                </div>
                {hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
              </div>
            </div>
          );
        }) : <div className="border-t border-border p-4"><p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Заявок регистрации нет.</p></div>}
      </section>

      <section className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[960px] grid-cols-[190px_220px_190px_220px_130px_220px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>ID устройства</span><span>Запрошенный аккаунт</span><span>Базовый владелец</span><span>Причина</span><span>Статус</span><span>Действия</span>
        </div>
        {loginRequests.length ? loginRequests.map((request) => (
          <div className="grid min-w-[960px] grid-cols-[190px_220px_190px_220px_130px_220px] gap-3 border-t border-border px-4 py-3 text-sm" key={request.request_id}>
            <span className="break-all">{request.device_id}</span>
            <span>{accountName(request)}</span>
            <span>{request.base_person_id ?? "Нет данных"}</span>
            <span>{request.reason ?? String(request.requested_account.reason ?? "Не указана")}</span>
            <Badge tone={statusTone(request.status)}>{registryStatusLabel(request.status)}</Badge>
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<Check className="h-4 w-4" />} onClick={() => onApproveLoginRequest(request)} size="sm" title="Разрешить вход в другой аккаунт для этого устройства" variant="outline">Подтвердить</Button>
              <Button leadingIcon={<X className="h-4 w-4" />} onClick={() => onRejectLoginRequest(request)} size="sm" title="Отклонить вход в другой аккаунт с причиной" variant="ghost">Отклонить</Button>
            </div>
          </div>
        )) : <div className="border-t border-border p-4"><p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Заявок на вход в другой аккаунт нет.</p></div>}
      </section>
    </div>
  );
}
