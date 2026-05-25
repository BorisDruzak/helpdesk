import { Check, X } from "lucide-react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import type { AdminAccountLoginRequest, AdminRegistrationClaim } from "../api";
import { formatDateTime, statusTone, type RegistrySelection } from "./registry-utils";

type Props = {
  claims: AdminRegistrationClaim[];
  loginRequests: AdminAccountLoginRequest[];
  onApproveClaim: (claim: AdminRegistrationClaim, replaceExisting?: boolean, override?: boolean) => void;
  onRejectClaim: (claim: AdminRegistrationClaim) => void;
  onApproveLoginRequest: (request: AdminAccountLoginRequest) => void;
  onRejectLoginRequest: (request: AdminAccountLoginRequest) => void;
  onSelect: (selection: RegistrySelection) => void;
};

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

export function RegistryRequestsTab({ claims, loginRequests, onApproveClaim, onApproveLoginRequest, onRejectClaim, onRejectLoginRequest, onSelect }: Props) {
  return (
    <div className="space-y-5">
      <section className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[1140px] grid-cols-[190px_190px_190px_150px_150px_120px_340px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>ПК</span><span>Device ID</span><span>Пользователь</span><span>Тип</span><span>Статус</span><span>Submitted</span><span>Действия</span>
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
              <span>{claim.relationship_type}</span>
              <Badge tone={statusTone(claim.status)}>{claim.status}</Badge>
              <span>{formatDateTime(claim.submitted_at)}</span>
              <div className="space-y-1">
                <div className="flex flex-wrap gap-2">
                  <Button disabled={!canApprove} leadingIcon={<Check className="h-4 w-4" />} onClick={() => onApproveClaim(claim)} size="sm" title={!canApprove ? "Нужно подтверждение пользователя или админский override" : undefined} variant="outline">Подтвердить</Button>
                  <Button disabled={!isConflict || (!canApprove && !claim.user_confirmed_at)} onClick={() => onApproveClaim(claim, true)} size="sm" variant="outline">С заменой</Button>
                  <Button disabled={isTerminal} onClick={() => onApproveClaim(claim, isConflict, true)} size="sm" variant="ghost">{isConflict ? "Админ с заменой" : "Админское подтверждение"}</Button>
                  <Button disabled={isTerminal} leadingIcon={<X className="h-4 w-4" />} onClick={() => onRejectClaim(claim)} size="sm" variant="ghost">Отклонить</Button>
                </div>
                {hint ? <p className="text-xs text-slate-500">{hint}</p> : null}
              </div>
            </div>
          );
        }) : <div className="border-t border-border p-4"><p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Заявок регистрации нет.</p></div>}
      </section>

      <section className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[960px] grid-cols-[190px_220px_190px_220px_130px_220px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>Device ID</span><span>Запрошенный аккаунт</span><span>Base owner</span><span>Причина</span><span>Статус</span><span>Действия</span>
        </div>
        {loginRequests.length ? loginRequests.map((request) => (
          <div className="grid min-w-[960px] grid-cols-[190px_220px_190px_220px_130px_220px] gap-3 border-t border-border px-4 py-3 text-sm" key={request.request_id}>
            <span className="break-all">{request.device_id}</span>
            <span>{accountName(request)}</span>
            <span>{request.base_person_id ?? "Нет данных"}</span>
            <span>{request.reason ?? String(request.requested_account.reason ?? "Не указана")}</span>
            <Badge tone={statusTone(request.status)}>{request.status}</Badge>
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<Check className="h-4 w-4" />} onClick={() => onApproveLoginRequest(request)} size="sm" variant="outline">Подтвердить</Button>
              <Button leadingIcon={<X className="h-4 w-4" />} onClick={() => onRejectLoginRequest(request)} size="sm" variant="ghost">Отклонить</Button>
            </div>
          </div>
        )) : <div className="border-t border-border p-4"><p className="rounded-lg border border-dashed border-border px-4 py-6 text-sm text-slate-500">Заявок на вход в другой аккаунт нет.</p></div>}
      </section>
    </div>
  );
}
