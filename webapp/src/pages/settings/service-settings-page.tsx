import {SettingsConfirmDialog} from "./settings-confirm-dialog";
import {SettingsLink} from "./settings-link";
import {useEffect, useState} from 'react';
import {useInRouterContext, useSearchParams} from 'react-router-dom';
import {PageHeading} from '../../components/ui/page-heading';
import {Button} from '../../components/ui/button';
import {useServiceSettings} from './use-service-settings';
import {ServiceSettingsSection} from './service-settings-section';
import {SettingsDraftGuard} from './settings-draft-guard';
import {TAB_ITEMS, type SettingsTab} from './settings-types';
import './settings.css';

function ServiceSettingsContent({section,onSection}:{section?:string|null;onSection?:(value:string)=>void}) {
 const model=useServiceSettings();
 const {activeTab,setActiveTab,dirty,setDirty,feedback,settingsQuery,payload,requestChange}=model;
 const [pendingSection,setPendingSection]=useState<string|null>(null);
 useEffect(()=>{if(TAB_ITEMS.some(item=>item.value===section))setActiveTab(section as SettingsTab);},[section,setActiveTab]);
 useEffect(()=>{if(pendingSection&&!dirty){onSection?.(pendingSection);setPendingSection(null);}},[pendingSection,dirty,onSection]);
 const mutations=[model.workflowProfilesMutation,model.queueMutation,model.memberMutation,model.removeMemberMutation,model.olaMutation,model.routingMutation,model.policyMutation,model.slaTargetsMutation,model.priorityMatrixMutation,model.calendarMutation,model.resolutionMutation,model.deleteResolutionMutation];
 const busy=mutations.some(item=>item.isPending);
 const group=model.dirtyGroups;
 const saves={tickets:{mutation:model.workflowProfilesMutation,label:'профили',dirty:group.workflow},queues:group.queue?{mutation:model.queueMutation,label:'очередь',dirty:true}:group.ola?{mutation:model.olaMutation,label:'внутренние сроки',dirty:true}:group.member?{mutation:model.memberMutation,label:'участник',dirty:true}:{mutation:model.queueMutation,label:'очередь',dirty:false},routing:{mutation:model.routingMutation,label:'правило',dirty:group.routing},sla:group.policy?{mutation:model.policyMutation,label:'политика сроков',dirty:true}:group.sla?{mutation:model.slaTargetsMutation,label:'сроки',dirty:true}:group.matrix?{mutation:model.priorityMatrixMutation,label:'матрица',dirty:true}:{mutation:model.policyMutation,label:'политика сроков',dirty:false},calendars:{mutation:model.calendarMutation,label:'календарь',dirty:group.calendar},resolution:{mutation:model.resolutionMutation,label:'код решения',dirty:group.resolution}};
 const primary=saves[activeTab as keyof typeof saves];
 const canSave=activeTab==='queues'?model.canManageQueues:activeTab==='tickets'?model.canManageWorkflow:model.canManageRouting;
 function select(value:SettingsTab){if(value===activeTab)return;requestChange(()=>{model.discardDraft();setActiveTab(value);setPendingSection(value);});}
 return <section className="service-settings space-y-4">
  <SettingsDraftGuard dirty={dirty||busy}/>
  <PageHeading eyebrow="Администрирование" title="Настройки службы" description="Общие правила обработки обращений. Изменения действуют для службы поддержки."/>
  <div className="settings-layout">
   <nav aria-label="Разделы настроек службы" className="settings-navigation">
    <p className="px-3 text-xs font-semibold text-slate-600">Служба поддержки</p>
    {TAB_ITEMS.map(item=><button key={item.value} type="button" disabled={busy} aria-current={activeTab===item.value?'page':undefined} onClick={()=>select(item.value)} className={activeTab===item.value?'settings-nav-item settings-nav-active':'settings-nav-item'}>{item.label}</button>)}
    <SettingsLink className="settings-nav-item underline" href="/app/settings">Мои настройки</SettingsLink>
   </nav>
   <div className="min-w-0 space-y-4">
    <div className="settings-actions" aria-label="Действия с настройками">
     <p role="status" aria-live="polite" className="text-sm">{busy?'Сохраняем…':dirty?'Есть несохранённые изменения':'Изменения сохранены'}</p>
     <div className="flex flex-wrap gap-2">
      {dirty?<Button variant="outline" disabled={busy} onClick={()=>model.discardDraft()}>Отменить изменения</Button>:<Button variant="outline" disabled={busy||settingsQuery.isFetching} onClick={()=>void settingsQuery.refetch()}>Обновить</Button>}
      {primary?<Button disabled={!canSave||busy||!primary.dirty} onClick={()=>primary.mutation.mutate()}>Сохранить: {primary.label}</Button>:null}
     </div>
    </div>
    {payload&&!model.writeEnabled?<p role="note" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">Изменение общей конфигурации отключено на сервере. Доступен просмотр; профили процесса используют отдельное разрешение.</p>:null}
    {feedback?<p role={feedback.tone==='error'?'alert':'status'} aria-live="polite" className={feedback.tone==='error'?'text-rose-700':'text-emerald-800'}>{feedback.text}</p>:null}
    {settingsQuery.isPending?<p role="status">Загружаем настройки службы…</p>:null}
    {settingsQuery.isError?<div role="alert">Не удалось загрузить настройки службы. {payload?'Ранее загруженные данные сохранены.':'Повторите попытку.'}<Button variant="outline" disabled={dirty} onClick={()=>void settingsQuery.refetch()}>Повторить загрузку</Button></div>:null}
    {payload&&!payload.ticket_settings.operational_flags.admin_config_api_enabled?<p role="status">Управление конфигурацией отключено на сервере. Это не означает, что в службе нет настроек.</p>:payload?<fieldset disabled={busy} className="min-w-0" onChangeCapture={event=>model.markDirty((event.target as HTMLElement).dataset.settingsDraft)}><ServiceSettingsSection model={model}/></fieldset>:null}
   </div>
  </div>
  {model.pendingChange?<SettingsConfirmDialog description="Перейти к другой настройке и отменить текущие изменения?" cancelLabel="Продолжить редактирование" confirmLabel="Отменить и перейти" onCancel={()=>model.setPendingChange(null)} onConfirm={()=>model.confirmChange()}/>:null}
 </section>;
}
function RoutedServiceSettings(){const [params,setParams]=useSearchParams();return <ServiceSettingsContent section={params.get('section')} onSection={value=>setParams({section:value})}/>;}
export function ServiceSettingsPage(){return useInRouterContext()?<RoutedServiceSettings/>:<ServiceSettingsContent/>;}
