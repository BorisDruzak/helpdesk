import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "../../components/ui/button";
import { fetchEffectiveAccess, type AccessSummaryPayload } from "../access-control/api";
import { saveUserAccount, type UserAccount } from "./api";
import { fieldClass, labelClass, roleLabels } from "./model";
import { PermissionsFields } from "./permissions-fields";

type Props = { personId: string; initial: UserAccount; isNew: boolean; linking: boolean; archived: boolean; accessUnavailable?: boolean; tab: string; summary: AccessSummaryPayload; onSaved: (account: UserAccount) => void; onDirty: () => void };

function snapshotKey(account: UserAccount) {
  return JSON.stringify({ ...account, queue_ids: [...account.queue_ids].sort((a, b) => a - b), group_ids: [...account.group_ids].sort((a, b) => a - b) });
}

export function AccountEditor({ personId, initial, isNew, linking, archived, accessUnavailable, tab, summary, onSaved, onDirty }: Props) {
  const client = useQueryClient();
  const [account, setAccount] = useState<UserAccount>(() => ({ ...initial, queue_ids: [...initial.queue_ids], group_ids: [...initial.group_ids] }));
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [dirty, setDirty] = useState(false);
  const authoritativeKey = snapshotKey(initial);
  const [baselineKey, setBaselineKey] = useState(authoritativeKey);
  const serverChanged = authoritativeKey !== baselineKey;
  const effective = useQuery({ queryKey: ["admin-access-effective", initial.user_login, initial.actor_role], queryFn: () => fetchEffectiveAccess({ userLogin: initial.user_login, actorRole: initial.actor_role }), enabled: Boolean(initial.user_login) && !isNew, retry: false });
  const mutation = useMutation({
    mutationFn: () => saveUserAccount(personId, { ...account, user_login: account.user_login.trim(), reason: reason.trim(), ...(password ? { password } : {}) }),
    onSuccess: async (next) => {
      setPassword("");
      client.setQueryData<UserAccount[]>(["admin-user-accounts", personId], (current) => [...(current ?? []).filter((item) => item.user_login !== next.user_login), next]);
      await Promise.all([client.invalidateQueries({ queryKey: ["admin-registry"] }), client.invalidateQueries({ queryKey: ["admin-user-accounts", personId] }), client.invalidateQueries({ queryKey: ["admin-access-summary"] }), client.invalidateQueries({ queryKey: ["admin-access-audit"] }), client.invalidateQueries({ queryKey: ["admin-access-effective"] })]);
    },
  });
  useEffect(() => {
    if (!dirty && !mutation.isPending && serverChanged) {
      setAccount(JSON.parse(authoritativeKey) as UserAccount);
      setBaselineKey(authoritativeKey);
    }
  }, [authoritativeKey, dirty, mutation.isPending, serverChanged]);
  const change = (next: UserAccount) => { setAccount(next); setDirty(true); onDirty(); mutation.reset(); };
  return <form className="space-y-4" onSubmit={(event) => {
    event.preventDefault();
    if (serverChanged || accessUnavailable || archived || mutation.isPending) return;
    onDirty();
    mutation.mutate(undefined, { onSuccess: (next) => { setPassword(""); setReason(""); setDirty(false); onSaved(next); } });
  }}>
    {tab === "permissions" ? <p className="text-sm font-medium text-slate-700">{roleLabels[account.actor_role] || account.actor_role} · {account.is_active ? "Вход разрешён" : "Вход отключён"}</p> : null}
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-slate-50 p-3 sm:flex-row sm:items-end">
      <label className={`${labelClass} min-w-0 flex-1`}>Причина изменения<input className={fieldClass} value={reason} onChange={(event) => { setReason(event.target.value); onDirty(); }} placeholder="Например: назначение в техподдержку" required disabled={mutation.isPending} /></label>
      <Button className="shrink-0" leadingIcon={<Save aria-hidden="true" className="h-4 w-4" />} type="submit" disabled={mutation.isPending || archived || accessUnavailable || serverChanged || !account.user_login.trim() || !reason.trim() || (isNew && !password)}>{mutation.isPending ? "Сохраняем…" : "Сохранить доступ"}</Button>
    </div>
    {serverChanged && dirty && !mutation.isPending ? <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"><p>Запись изменилась на сервере. Черновик сохранён. Загрузите актуальное состояние, прежде чем снова изменять доступ.</p><Button className="mt-2 max-w-full whitespace-normal" size="sm" variant="outline" onClick={() => { setAccount(JSON.parse(authoritativeKey) as UserAccount); setBaselineKey(authoritativeKey); setPassword(""); setDirty(false); mutation.reset(); }}>Отменить черновик и загрузить актуальные данные</Button></div> : null}
    {mutation.isError ? <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{mutation.error.message} Черновик сохранён, исправьте данные и повторите попытку.</p> : null}
    {archived ? <p role="alert" className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">Профиль в архиве. Для изменения доступа сначала восстановите пользователя.</p> : null}
    <fieldset disabled={mutation.isPending || archived || accessUnavailable} className={tab === "account" ? "space-y-4" : "hidden"}>
      {linking ? <p className="text-sm text-brand-800">Этот логин будет привязан к выбранному пользователю при сохранении.</p> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <label className={labelClass}>Логин<input autoComplete="off" className={fieldClass} value={account.user_login} readOnly={!isNew} onChange={(event) => change({ ...account, user_login: event.target.value })} required /></label>
        <label className={labelClass}>Роль<select aria-label="Роль" className={fieldClass} value={account.actor_role} onChange={(event) => change({ ...account, actor_role: event.target.value })}>{Object.entries(roleLabels).map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
        {isNew ? <label className={labelClass}>Пароль для нового входа<input aria-label="Пароль для нового входа" autoComplete="new-password" className={fieldClass} type="password" value={password} onChange={(event) => { setPassword(event.target.value); setDirty(true); onDirty(); }} required /><span className="text-xs font-normal text-slate-500">Пароль проверяется по политике безопасности при сохранении.</span></label> : <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-500">Логин закреплён за этой записью. Смена забытого пароля доступна в дополнительных операциях.</div>}
        <label className="flex items-center gap-2 text-sm text-slate-700"><input className="accent-brand-600" type="checkbox" checked={account.is_active} onChange={(event) => change({ ...account, is_active: event.target.checked })} />Учётная запись активна</label>
      </div>
      <p className="text-xs leading-5 text-slate-500">Роль, состояние входа, прямые очереди и группы сохраняются вместе.</p>
    </fieldset>
    <fieldset disabled={mutation.isPending || archived || accessUnavailable} className={tab === "permissions" ? "block" : "hidden"}><PermissionsFields account={account} onChange={change} summary={summary} effective={effective.data} effectiveError={effective.isError} /></fieldset>
    {dirty ? <p className="text-xs text-amber-700">Есть несохранённые изменения</p> : null}
  </form>;
}
