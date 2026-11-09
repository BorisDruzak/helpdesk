import {SettingsLink} from "./settings-link";
import {useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {fetchAdminRegistry} from '../../features/admin/api';
import {Button} from '../../components/ui/button';
import {Select} from '../../components/ui/select';
import {Input} from '../../components/ui/input';
import {SettingsField} from './settings-fields';
import type {ServiceSettingsModel} from './use-service-settings';

export function QueueMemberPicker({model}:{model:ServiceSettingsModel}) {
 const [open,setOpen]=useState(false);
 const query=useQuery({queryKey:['admin-registry'],queryFn:fetchAdminRegistry,enabled:open&&model.canManageQueues,retry:false});
 const accounts=query.data?.ui_users?.filter(user=>user.is_active&&(user.actor_role==='support'||user.actor_role==='admin'))??[];
 return <div className="space-y-3">
  {!open?<Button variant="outline" disabled={!model.canManageQueues||!model.selectedQueue} onClick={()=>setOpen(true)}>Выбрать сотрудника</Button>:<>
   {query.isPending?<p role="status">Загружаем сотрудников…</p>:query.isError?<p role="alert">Не удалось загрузить сотрудников. Проверьте доступ к разделу «Пользователи».</p>:<SettingsField label="Сотрудник"><Select data-settings-draft="member" value={model.newMemberActorId} onChange={event=>model.setNewMemberActorId(event.target.value)}><option value="">Выберите сотрудника</option>{accounts.map(user=><option key={user.user_login} value={user.user_login}>{user.linked_person_name||user.user_login} · {user.user_login}</option>)}</Select></SettingsField>}
   <SettingsField label="Роль в очереди (необязательно)"><Input data-settings-draft="member" value={model.newMemberRole} onChange={event=>model.setNewMemberRole(event.target.value)} placeholder="Например, дежурный специалист"/></SettingsField>
  </>}
  <Button disabled={!model.canManageQueues||model.memberMutation.isPending||!model.selectedQueue||!model.newMemberActorId} onClick={()=>model.memberMutation.mutate()}>Добавить / обновить участника</Button>
  <SettingsLink className="block text-sm text-brand-800 underline" href="/app/admin/users">Управлять пользователями и доступом</SettingsLink>
 </div>;
}
