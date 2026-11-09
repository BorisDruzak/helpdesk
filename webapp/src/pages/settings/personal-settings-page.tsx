import {SettingsLink} from "./settings-link";
import {useState} from 'react';
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query';
import {PageHeading} from '../../components/ui/page-heading';
import {Button} from '../../components/ui/button';
import {useSession} from '../../features/auth/session-provider';
import {hasPermission} from '../../features/auth/permissions';
import {BrowserPushControl} from '../../features/notifications/browser-push-control';
import {fetchNotificationSettings, saveNotificationPreferences} from '../../features/settings/api';
import {savePanelPreferences} from '../../shared/ui/workspace-panel-preferences';
import {NOTIFICATION_CATALOG} from './settings-types';

export function PersonalSettingsPage() {
  const {session}=useSession();
  const client=useQueryClient();
  const login=session?.user_login??'';
  const [feedback,setFeedback]=useState('');
  const [tab,setTab]=useState<'notifications'|'workspace'>('notifications');
  const query=useQuery({queryKey:['notification-settings',login],queryFn:fetchNotificationSettings,retry:false});
  const mutation=useMutation({mutationFn:saveNotificationPreferences,
    onSuccess:async(data)=>{client.setQueryData(['notification-settings',login],data);setFeedback('Настройки уведомлений сохранены.');},
    onError:()=>setFeedback('Не удалось сохранить настройки. Прежние значения сохранены; повторите попытку.')});
  const prefs=query.data?.preferences;
  const pending=mutation.isPending;
  function resetPanels() {
    if(!login){setFeedback('Не удалось определить учётную запись. Обновите страницу.');return;}
    const saved=savePanelPreferences(login,'support',{navigationCollapsed:false,ticketListCollapsed:false,navigationPinned:false});
    setFeedback(saved?'Расположение панелей сброшено. Изменение действует в этом браузере при следующем открытии рабочей зоны.':'Не удалось сохранить расположение панелей в этом браузере.');
  }
  return <section className="space-y-5 max-w-5xl">
    <PageHeading eyebrow="Личные предпочтения" title="Мои настройки" description="Ваши уведомления и рабочее место. Изменения не влияют на других сотрудников."/>
    <nav aria-label="Личные настройки" className="flex flex-wrap gap-2">
      <Button variant={tab==='notifications'?'primary':'outline'} aria-current={tab==='notifications'?'page':undefined} onClick={()=>setTab('notifications')}>Уведомления</Button>
      <Button variant={tab==='workspace'?'primary':'outline'} aria-current={tab==='workspace'?'page':undefined} onClick={()=>setTab('workspace')}>Рабочее место</Button>
    </nav>
    {feedback?<p role={mutation.isError?'alert':'status'} aria-live="polite" className="rounded-panel border border-border bg-white p-4">{feedback}</p>:null}
    {tab==='notifications'?<div className="space-y-5">
      <div className="rounded-panel border border-border bg-white p-5 space-y-4">
        <h2 className="text-lg font-semibold">События в обращениях</h2>
        <p className="text-sm text-slate-600">Переключатели сохраняются сразу и действуют только для вашей учётной записи. Доступ к обращениям определяется вашими правами.</p>
        {query.isPending?<p role="status">Загружаем настройки уведомлений…</p>:query.isError?<div role="alert">Не удалось загрузить настройки уведомлений. <Button variant="outline" onClick={()=>void query.refetch()}>Повторить</Button></div>:prefs?<fieldset disabled={pending} className="space-y-3">
          {NOTIFICATION_CATALOG.map(item=><label key={item.eventType} className="flex items-start gap-3 rounded-lg border border-border p-3"><input className="mt-1 h-4 w-4" type="checkbox" checked={!prefs.muted_event_types.includes(item.eventType)&&!(item.eventType==="internal_note"&&prefs.mute_internal)} onChange={event=>{const muted=new Set(prefs.muted_event_types);if(event.target.checked)muted.delete(item.eventType);else muted.add(item.eventType);mutation.mutate({muted_event_types:[...muted],...(item.eventType==="internal_note"?{mute_internal:!event.target.checked}:{})});}}/><span><span className="block font-medium">{item.title}</span><span className="block text-sm text-slate-600">{item.description}</span></span></label>)}
          <label className="flex gap-3 p-3"><input type="checkbox" checked={prefs.suppress_self} onChange={event=>mutation.mutate({suppress_self:event.target.checked})}/>Не уведомлять о своих действиях</label>

        </fieldset>:null}
        {pending?<p role="status">Сохраняем…</p>:null}
      </div>
      <div className="rounded-panel border border-border bg-white p-5"><h2 className="text-lg font-semibold">Уведомления в этом браузере</h2><p className="text-sm text-slate-600 mt-2">Разрешение браузера настраивается отдельно от событий вашей учётной записи.</p><BrowserPushControl userLogin={login}/></div>
    </div>:<div className="rounded-panel border border-border bg-white p-5 space-y-4"><h2 className="text-lg font-semibold">Панели рабочей зоны</h2><p className="text-sm text-slate-600">Ширина и расположение панелей сохраняются при работе с очередью. Можно вернуть начальное расположение бокового меню и списка обращений в этом браузере.</p><Button variant="outline" onClick={resetPanels}>Сбросить расположение панелей</Button><SettingsLink className="block text-brand-800 underline" href="/app/tickets">Открыть очередь обращений</SettingsLink></div>}
    {session?.available_workspaces?.includes('admin')&&hasPermission(session,'settings.view')?<SettingsLink className="inline-block text-brand-800 underline" href="/app/admin/settings">Настройки службы</SettingsLink>:null}
  </section>;
}
