import type { SupportWorkspaceContext } from "../../../features/queues/support-workspace-model";

const supplied = (value: string | null | undefined) => value && !/^не указан[ао]?$/i.test(value.trim());
const accountModes: Record<string, string> = {
  browser_no_device: "Обращение из браузера без устройства",
  registration_pending: "Ожидает подтверждения регистрации",
  registered: "Зарегистрированный аккаунт",
};

export function TicketRequesterContext({ requester }: { requester: SupportWorkspaceContext["requester"] }) {
  const contacts = [["Телефон", requester.phone], ["Электронная почта", requester.email], ["Подразделение", requester.department], ["Место", requester.location]].filter(([, value]) => supplied(value));
  return <section className="rounded-xl border border-white/10 bg-[#111f33] p-4" aria-label="Заявитель">
    <h3 className="font-semibold">Заявитель</h3>
    <p className="mt-2 font-semibold">{requester.name}</p>
    {contacts.length ? <dl className="mt-3 grid gap-2 text-sm">{contacts.map(([label, value]) => <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd>{value}</dd></div>)}</dl> : <p className="mt-2 text-sm text-slate-500">Контактные данные в профиле не заполнены.</p>}
    {requester.sourceLabel !== "Профиль: не указан" ? <p className="mt-3 text-xs text-slate-500">{requester.sourceLabel}</p> : null}
    {requester.accountWarning === "ticket_created_from_other_account_on_registered_device" ? <div className="mt-3 rounded-lg border border-amber-300/30 bg-amber-500/10 p-3 text-sm">
      <p className="font-semibold">Обращение создано с другого аккаунта на зарегистрированном устройстве.</p>
      {requester.activeDeviceOwner ? <p>Владелец устройства: {requester.activeDeviceOwner}</p> : null}
    </div> : null}
    {requester.accountMode || requester.accountLogin ? <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold">Аккаунт обращения</summary>
      <dl className="mt-2 grid gap-2">{requester.accountMode ? <div><dt className="text-xs text-slate-500">Способ обращения</dt><dd>{accountModes[requester.accountMode] ?? "Через учётную запись"}</dd></div> : null}
        {[["Заявленное имя", requester.accountDeclaredName], ["Логин", requester.accountLogin], ["Телефон аккаунта", requester.accountPhone], ["Почта аккаунта", requester.accountEmail], ["Причина", requester.accountReason], ["Проверка аккаунта", requester.accountVerification]].filter(([, value]) => supplied(value)).map(([label, value]) => <div key={label}><dt className="text-xs text-slate-500">{label}</dt><dd>{value}</dd></div>)}
      </dl>
    </details> : null}
  </section>;
}
