import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {act, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {ServiceSettingsPage as SettingsPage} from './service-settings-page';
import {createSettingsPayload, jsonResponse} from './settings-test-fixtures';

afterEach(()=>vi.unstubAllGlobals());
function setup(withRules=false,delayCreate=false,writeEnabled=true) {
  const payload=createSettingsPayload();
  payload.ticket_settings.operational_flags.admin_config_write_enabled=writeEnabled;
  if(withRules)payload.routing_rules=[{id:10,enabled:true,priority_order:10,target_queue_id:1,target_queue_name:'ServiceDesk L1',condition_json:{field:'request_kind',op:'eq',value:'old'}}];
  payload.sla_policies=[{id:20,name:'Стандартная',timezone:'UTC',calendar_id:null,calendar_name:null,is_default:true,is_active:true,open_tickets_count:0,business_hours_json:{mode:'always_on'},targets:[{priority:'P1',first_response_min:15,resolution_min:240}],priority_matrix:[]}];
  payload.calendars=[{id:30,code:'weekday',name:'Будни',timezone:'UTC',is_active:true,weekly_hours_json:{mon:[['09:00','18:00']]},holidays_json:{dates:[]},created_at:null,updated_at:null}];
  payload.resolution_codes=[{code:'fixed',name:'Исправлено',is_active:true,sort_order:1,usage_count:0}];
  let waitForCreate=false;
  const fetcher=vi.fn(async(input:RequestInfo|URL,init?:RequestInit)=>{
    const url=String(input);
    if(url==='/api/web/settings') {if(waitForCreate){await new Promise(resolve=>setTimeout(resolve,75));waitForCreate=false;}return jsonResponse({status:'success',data:structuredClone(payload)});}
    if(delayCreate&&init?.method==='POST'){
      const data=JSON.parse(String(init.body));waitForCreate=true;
      if(url.endsWith('/queues'))payload.queues.push({...payload.queues[0],id:2,...data});
      if(url.endsWith('/sla_policies'))payload.sla_policies.push({...payload.sla_policies[0],id:21,...data});
      if(url.endsWith('/calendars'))payload.calendars.push({...payload.calendars[0],id:31,...data});
      if(url.endsWith('/resolution_codes'))payload.resolution_codes.push({...payload.resolution_codes[0],code:'new_result',...data});
      if(url.endsWith('/routing_rules'))payload.routing_rules.push({...payload.routing_rules[0],id:11,...data});
    }
    if(init?.method==='POST'||init?.method==='PUT') return jsonResponse({status:'ok',queue:{id:2},sla_policy:{id:21},calendar:{id:31},resolution_code:{code:'new_result'},routing_rule:{id:11}});
    if(url==='/api/web/admin/tech/alerts') return jsonResponse({status:'ok',alerts:[{id:'a1',kind:'observer_degradation',severity:'warning',summary:'Нарушена обработка событий',details:{},link:'/app/admin/observer'}]});
    if(url==='/api/web/notifications/preferences') return jsonResponse({status:'ok',preferences:{mute_internal:false,muted_event_types:[],suppress_self:true}});
    if(url.startsWith('/api/web/notifications')) return jsonResponse({status:'ok',notifications:[]});
    throw new Error(`Unexpected request ${url} ${init?.method}`);
  });
  vi.stubGlobal('fetch',fetcher);
  const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
  render(<QueryClientProvider client={client}><SettingsPage/></QueryClientProvider>);
  return {fetcher,client,payload};
}

describe('settings audited regressions',()=>{
  it('creates a new queue without updating an existing queue',async()=>{
    const {fetcher}=setup();fireEvent.click(await screen.findByRole('button',{name:'Очереди'}));
    fireEvent.click(screen.getByRole('button',{name:'Новая очередь'}));
    fireEvent.change(screen.getByLabelText('Код'),{target:{value:'new_queue'}});
    fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Новая группа'}});
    fireEvent.click(screen.getByRole('button',{name:'Сохранить очередь'}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([url,init])=>url==='/api/web/settings/queues'&&init?.method==='POST')).toBe(true));
    expect(fetcher.mock.calls.some(([url])=>String(url).includes('/queues/1'))).toBe(false);
  });
  it('allows a new result code when codes already exist',async()=>{
    setup();fireEvent.click(await screen.findByRole('button',{name:'Коды решения'}));
    fireEvent.click(screen.getByRole('button',{name:'Новый код'}));
    expect(screen.getByLabelText('Код')).toBeEnabled();
    expect(screen.getByRole('heading',{name:'Новый код решения'})).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Удалить код'})).toBeDisabled();
  });
  it('does not fabricate zero SLA values for absent targets',async()=>{
    setup();fireEvent.click(await screen.findByRole('button',{name:'Сроки'}));
    expect(screen.getByRole('spinbutton',{name:'P0: первый ответ, минут'})).toHaveValue(null);
    expect(screen.getByRole('spinbutton',{name:'P1: первый ответ, минут'})).toHaveValue(15);
  });
  it('keeps an unsaved queue name when server data is refreshed',async()=>{
    const {client,payload}=setup();fireEvent.click(await screen.findByRole('button',{name:'Очереди'}));
    fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Мой черновик'}});
    await act(async()=>{client.setQueryData(['web-settings'],{...payload,queues:payload.queues.map(q=>({...q,name:'Изменено другим администратором'}))});await new Promise(resolve=>setTimeout(resolve,25));});
    await waitFor(()=>expect(screen.getByLabelText('Название')).toHaveValue('Мой черновик'));
  });
  it('renders the actual technical alert summary and details link',async()=>{
    setup();fireEvent.click(await screen.findByRole('button',{name:'Состояние системы'}));
    expect(await screen.findByText('Нарушена обработка событий')).toBeInTheDocument();
    expect(screen.getByRole('link',{name:'Подробнее'})).toHaveAttribute('href','/app/admin/observer');
  });
  it('retains a different unsaved form when internal targets are saved',async()=>{
    const {fetcher}=setup();fireEvent.click(await screen.findByRole('button',{name:'Очереди'}));
    fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Не потерять'}});
    fireEvent.change(screen.getByRole('spinbutton',{name:'P1: принятие, минут'}),{target:{value:'15'}});
    fireEvent.change(screen.getByRole('spinbutton',{name:'P1: обработка, минут'}),{target:{value:'120'}});
    fireEvent.click(screen.getByRole('button',{name:'Сохранить внутренние сроки'}));
    await screen.findByText('Внутренние сроки очереди сохранены.');
    expect(screen.getByLabelText('Название')).toHaveValue('Не потерять');
    expect(screen.getByText('Есть несохранённые изменения')).toBeInTheDocument();
  });
  it('asks before switching sections with an unsaved draft and can discard it',async()=>{
    setup();fireEvent.click(await screen.findByRole('button',{name:'Очереди'}));
    fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Черновик'}});
    fireEvent.click(screen.getByRole('button',{name:'Календари'}));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button',{name:'Продолжить редактирование'}));
    expect(screen.getByLabelText('Название')).toHaveValue('Черновик');
    fireEvent.click(screen.getByRole('button',{name:'Календари'}));
    fireEvent.click(screen.getByRole('button',{name:'Отменить и перейти'}));
    expect(screen.getByText('Рабочая неделя')).toBeInTheDocument();
    expect(screen.getByRole('button',{name:'Сохранить календарь'})).toBeInTheDocument();
  });
  it.each([['Сроки','Новая политика','Сохранить политику сроков','/api/web/settings/sla_policies'],['Календари','Новый календарь','Сохранить календарь','/api/web/settings/calendars'],['Коды решения','Новый код','Сохранить код','/api/web/settings/resolution_codes']])('uses POST for a new object in %s',async(tab,create,save,url)=>{
    const {fetcher}=setup();fireEvent.click(await screen.findByRole('button',{name:tab}));fireEvent.click(screen.getByRole('button',{name:create}));
    if(tab!=='Сроки')fireEvent.change(screen.getByLabelText('Код'),{target:{value:'new_result'}});
    fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Новая настройка'}});
    fireEvent.click(screen.getByRole('button',{name:save}));
    await waitFor(()=>expect(fetcher.mock.calls.some(([target,init])=>target===url&&init?.method==='POST')).toBe(true));
  });
  it('edits general workflow fields without reading an expired event',async()=>{
    setup();fireEvent.click(await screen.findByRole('button',{name:'Тикеты'}));
    fireEvent.change(screen.getByLabelText('Название'),{target:{value:'Новый процесс'}});
    expect(screen.getByLabelText('Название')).toHaveValue('Новый процесс');
    fireEvent.click(screen.getByRole('checkbox',{name:'Требует согласование'}));
    expect(screen.getByRole('checkbox',{name:'Требует согласование'})).toBeChecked();
  });
  it('confirms before replacing an edited routing rule with a new rule',async()=>{
    setup(true);fireEvent.click(await screen.findByRole('button',{name:'Маршрутизация'}));
    fireEvent.change(screen.getByLabelText('Значение'),{target:{value:'my draft'}});
    fireEvent.click(screen.getByRole('button',{name:'Новое правило'}));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
  });
  it('does not save a deleted routing rule onto another rule',async()=>{
    const {client,payload,fetcher}=setup(true);fireEvent.click(await screen.findByRole('button',{name:'Маршрутизация'}));
    fireEvent.change(screen.getByLabelText('Значение'),{target:{value:'my draft'}});
    await act(async()=>{client.setQueryData(['web-settings'],{...payload,routing_rules:[{...payload.routing_rules[0],id:11}]});await new Promise(resolve=>setTimeout(resolve,25));});
    fireEvent.click(screen.getByRole('button',{name:'Сохранить правило'}));
    expect(await screen.findByRole('alert')).toHaveTextContent('больше недоступно');
    expect(fetcher.mock.calls.some(([url,init])=>String(url).endsWith('/routing_rules/11')&&init?.method!=='GET')).toBe(false);
  });
  it.each([
    ['Очереди','Новая очередь','Сохранить очередь','Настройки очереди сохранены.'],
    ['Сроки','Новая политика','Сохранить политику сроков','Политика сроков сохранена.'],
    ['Календари','Новый календарь','Сохранить календарь','Календарь сохранён.'],
    ['Коды решения','Новый код','Сохранить код','Код решения сохранён.'],
    ['Маршрутизация','Новое правило','Сохранить правило','Правило маршрутизации сохранено.']
  ])('selects the created object after slow refresh in %s',async(tab,create,save,message)=>{
    setup(true,true);fireEvent.click(await screen.findByRole('button',{name:tab}));
    fireEvent.click(screen.getByRole('button',{name:create}));
    if(tab!=='Маршрутизация'&&tab!=='Сроки')fireEvent.change(screen.getByLabelText('Код'),{target:{value:'new_result'}});
    fireEvent.change(screen.getByLabelText(tab==='Маршрутизация'?'Значение':'Название'),{target:{value:'Созданная настройка'}});
    fireEvent.click(screen.getByRole('button',{name:save}));
    await screen.findByText(message);
    await waitFor(()=>expect(screen.getByLabelText(tab==='Маршрутизация'?'Значение':'Название')).toHaveValue('Созданная настройка'));
  });
  it('honors the server write switch instead of offering forbidden config writes',async()=>{
    setup(false,false,false);
    fireEvent.click(await screen.findByRole('button',{name:'Очереди'}));
    expect(screen.getByRole('button',{name:'Новая очередь'})).toBeDisabled();
    expect(screen.getByText('Изменение общей конфигурации отключено на сервере.')).toBeInTheDocument();
  });
});
