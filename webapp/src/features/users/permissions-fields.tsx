import type { AccessEffectivePayload, AccessSummaryPayload } from "../access-control/api";
import type { UserAccount } from "./api";
import { toggleId } from "./model";

export function PermissionsFields({ account, onChange, summary, effective, effectiveError }: {
  account: UserAccount; onChange: (next: UserAccount) => void; summary: AccessSummaryPayload; effective?: AccessEffectivePayload; effectiveError?: boolean;
}) {
  const inherited = summary.access_groups.filter((group) => group.is_active && account.group_ids.includes(group.group_id)).flatMap((group) => group.queue_grants);
  const inheritedNames = [...new Set(inherited.map((queue) => queue.queue_name))];
  return <div className="grid gap-5 lg:grid-cols-2">
    <fieldset className="min-w-0"><legend className="mb-1 text-sm font-semibold text-slate-900">Прямой доступ к очередям</legend><p className="mb-3 text-xs leading-5 text-slate-500">Выберите рабочие очереди. Доступ через группы показан отдельно.</p>
      <div className="space-y-2">{summary.queues.map((queue) => <label key={queue.queue_id} className="flex items-start gap-2.5 rounded-lg border border-border px-3 py-2 text-sm text-slate-700">
        <input className="mt-1 accent-brand-600" type="checkbox" checked={account.queue_ids.includes(queue.queue_id)} disabled={!queue.is_active && !account.queue_ids.includes(queue.queue_id)} onChange={() => onChange({ ...account, queue_ids: toggleId(account.queue_ids, queue.queue_id) })} aria-label={queue.queue_name} />
        <span className="min-w-0 break-words">{queue.queue_name}{!queue.is_active ? <span className="block text-xs text-amber-700">Неактивна · можно снять назначение</span> : null}</span>
      </label>)}{!summary.queues.length ? <p className="text-sm text-slate-500">Очереди ещё не настроены.</p> : null}</div>
    </fieldset>
    <fieldset className="min-w-0"><legend className="mb-1 text-sm font-semibold text-slate-900">Группы доступа</legend><p className="mb-3 text-xs leading-5 text-slate-500">Группы дополняют базовую роль правами и очередями.</p>
      <div className="space-y-2">{summary.access_groups.map((group) => <label key={group.group_id} className="flex items-start gap-2.5 rounded-lg border border-border px-3 py-2 text-sm text-slate-700">
        <input className="mt-1 accent-brand-600" type="checkbox" checked={account.group_ids.includes(group.group_id)} disabled={!group.is_active && !account.group_ids.includes(group.group_id)} onChange={() => onChange({ ...account, group_ids: toggleId(account.group_ids, group.group_id) })} aria-label={group.name} />
        <span className="min-w-0 break-words">{group.name}<span className="block text-xs text-slate-500">{!group.is_active ? "Неактивна · можно снять назначение" : group.description}</span></span>
      </label>)}</div>
      {inheritedNames.length ? <p className="mt-3 rounded-lg bg-brand-50 px-3 py-2 text-xs leading-5 text-brand-800">Через группы: {inheritedNames.join(", ")}. Эти очереди сохраняются независимо от прямых назначений.</p> : null}
      {effective ? <p className="mt-3 text-xs leading-5 text-slate-500">Сохранённый доступ: {effective.queues.length} очередей, {effective.permissions.length} разрешений. Итог: базовая роль + группы + прямые очереди.</p> : null}
      {effectiveError ? <p role="alert" className="mt-3 text-xs text-amber-800">Не удалось рассчитать сохранённый доступ. Проверьте назначения после сохранения.</p> : null}
    </fieldset>
  </div>;
}
