import {SettingsLink} from "./settings-link";
import {Button} from '../../components/ui/button';
import type {ServiceSettingsModel} from './use-service-settings';

export function NotificationsSettingsSection({model}:{model:ServiceSettingsModel}) {
 const query=model.techAlertsQuery;
 return <section className="rounded-panel border border-border bg-white p-5 space-y-4" aria-labelledby="service-health-title">
   <h2 id="service-health-title" className="text-lg font-semibold">Состояние системы</h2>
   <p className="text-sm text-slate-600">Технические события службы. Личные уведомления настраиваются в разделе «Мои настройки».</p>
   {query.isPending?<p role="status">Проверяем состояние сервиса…</p>:query.isError?<div role="alert">Не удалось загрузить предупреждения. Состояние сервиса неизвестно. <Button variant="outline" onClick={()=>void query.refetch()}>Повторить</Button></div>:query.data?.alerts.length?<ul className="space-y-3">{query.data.alerts.map(alert=><li key={alert.id} className="rounded-lg border border-border p-4">
    <p className="font-medium">{alert.summary||'Техническое событие'}</p>
    <p className="mt-1 text-sm text-slate-600">{alert.severity==='critical'||alert.severity==='danger'?'Требует срочного внимания':alert.severity==='warning'?'Требует проверки':'Информация'}</p>
    {alert.link?.startsWith('/app/')?<SettingsLink className="mt-2 inline-block text-brand-800 underline" href={alert.link}>Подробнее</SettingsLink>:null}
   </li>)}</ul>:<p>Активных технических предупреждений нет.</p>}
 </section>;
}
