// Local demonstration domain. No Helpdesk/Endpoint requests are made.
export const STORAGE_KEY = 'helpdesk-guided-v3-demo-1';
export const kindNames = {question:'Вопрос',instruction:'Инструкция',diagnostic:'Диагностика',decision:'Условие',review:'Проверка перед отправкой',ticket:'Создать обращение',finish:'Завершить без обращения'};
export const policyLibrary = {
  routing:[{id:'workplace',name:'Поддержка рабочих мест',queue:'Поддержка рабочих мест'},{id:'printing',name:'Специалисты по печати',queue:'Специалисты по печати'}],
  priority:[{id:'impact',name:'Масштаб и срочность'}],
  sla:[{id:'standard',name:'Рабочее место · стандарт',response:'1 рабочий час',resolution:'8 рабочих часов'},{id:'critical',name:'Критичное рабочее место',response:'30 рабочих минут',resolution:'4 рабочих часа'}],
  approval:[{id:'none',name:'Без согласования'},{id:'manager',name:'Руководитель подразделения'}],
};
export function initialData(){
  const d={revision:1,title:'Проблемы с печатью',categories:[{id:'printers',title:'Принтеры',parent:'Оборудование'},{id:'software',title:'Программы',parent:'Рабочее место'}],
    entries:[
      {id:'not-printing',title:'Не печатает',description:'Документ не выходит из принтера',synonyms:'принтер не работает, нет печати, не распечатывает',category:'printers',start:'impact',status:'published',scenario:'printing'},
      {id:'paper-jam',title:'Застряла бумага',description:'Бумага застряла или принтер сообщает о замятии',synonyms:'замятие, бумажная пробка, зажевало бумагу',category:'printers',start:'jam',status:'published',scenario:'printing'},
      {id:'pale-print',title:'Бледная печать',description:'Текст бледный, полосы или пропуски на листе',synonyms:'тускло, полосы, плохо печатает, тонер',category:'printers',start:'quality',status:'published',scenario:'printing'},
    ],blocks:[
      {id:'jam',kind:'instruction',title:'Безопасно устраните замятие',body:'Отключите принтер и дождитесь остывания. Удалите застрявший лист по инструкции производителя, без усилия. Если лист не выходит, обратитесь в поддержку.',position:{x:0,y:0}},
      {id:'quality',kind:'instruction',title:'Проверьте качество печати',body:'Посмотрите, есть ли предупреждение о тонере. Попробуйте напечатать тестовую страницу. Не вскрывайте картридж и не меняйте настройки обслуживания.',position:{x:540,y:0}},
      {id:'impact',kind:'question',title:'Кто не может печатать?',choices:['Только я','Несколько человек','Весь отдел','Не знаю'],required:true,influences:['impact','routing'],position:{x:270,y:140}},
      {id:'urgency',kind:'question',title:'Насколько срочно нужна печать?',choices:['Можно подождать','Работа остановилась','Не знаю'],required:true,influences:['urgency'],position:{x:270,y:265}},
      {id:'paper',kind:'instruction',title:'Проверьте бумагу и подключение',body:'Убедитесь, что бумага загружена, принтер включён и на экране нет предупреждений. Попробуйте напечатать тестовую страницу.',position:{x:270,y:390}},
      {id:'diagnostic',kind:'diagnostic',title:'Проверка принтера',consent:true,timeout:30,position:{x:270,y:515}},
      {id:'resolved',kind:'decision',title:'Печать восстановилась?',position:{x:270,y:640}},
      {id:'finish',kind:'finish',title:'Завершить без обращения',message:'Рады, что печать восстановилась. Если проблема повторится, мы поможем.',position:{x:15,y:775}},
      {id:'review',kind:'review',title:'Проверить и передать в поддержку',position:{x:530,y:775}},
      {id:'ticket',kind:'ticket',title:'Создать обращение',position:{x:530,y:900}},
    ],edges:[
      {id:'jam-impact',source:'jam',target:'impact',label:'Продолжить'},
      {id:'quality-impact',source:'quality',target:'impact',label:'Продолжить'},
      {id:'impact-urgency',source:'impact',target:'urgency'},
      {id:'urgency-paper',source:'urgency',target:'paper'},
      {id:'paper-diagnostic',source:'paper',target:'diagnostic'},
      {id:'diagnostic-resolved',source:'diagnostic',target:'resolved',label:'Ручная проверка'},
      {id:'resolved-finish',source:'resolved',target:'finish',when:'yes',label:'Да'},
      {id:'resolved-review',source:'resolved',target:'review',when:'no',label:'Нет / Не знаю'},
      {id:'review-ticket',source:'review',target:'ticket'},
    ],policies:{priority:'impact',routing:'workplace',sla:'standard',approval:'none'},versions:[],testReceipt:null};
  d.versions=[{version:3,date:'11.10.2026',comment:'Начальная опубликованная версия',snapshot:snapshot(d)}];
  return d;
}
export const clone = x => JSON.parse(JSON.stringify(x));
function settleVisibility(d,s){
  let next=s;
  for(let i=0;i<40;i++){
    const b=block(d,next.current);
    if(!b||b.kind!=='question'||b.visibleWhen!=='department'||next.answers.impact==='Весь отдел')return next;
    const edge=d.edges.find(e=>e.source===b.id);
    if(!edge||!block(d,edge.target))return {...next,error:'Для скрытого вопроса не настроен следующий шаг.'};
    next={...next,current:edge.target,history:[...next.history.slice(0,-1),edge.target]};
  }
  return {...next,error:'Маршрут содержит цикл.'};
}
export function snapshot(d){return clone({title:d.title,categories:d.categories,entries:d.entries,blocks:d.blocks,edges:d.edges,policies:d.policies});}
export function fingerprint(d){return JSON.stringify(snapshot(d));}
export function block(d,id){return d.blocks.find(b=>b.id===id);}
export function processing(d,answers={}){
  const route=policyLibrary.routing.find(p=>p.id===d.policies.routing);
  const sla=policyLibrary.sla.find(p=>p.id===d.policies.sla);
  const approval=policyLibrary.approval.find(p=>p.id===d.policies.approval);
  const big=answers.impact==='Весь отдел';
  const urgent=answers.urgency==='Работа остановилась';
  const impactEnabled=block(d,'impact')?.influences?.includes('impact');
  const urgencyEnabled=block(d,'urgency')?.influences?.includes('urgency');
  const routedByImpact=route?.id==='workplace'&&big&&block(d,'impact')?.influences?.includes('routing');
  return {queue:routedByImpact?'Специалисты по печати':route?.queue||'Очередь недоступна',priority:(big&&impactEnabled&&urgent&&urgencyEnabled)?'P1 · Высокий':(big&&impactEnabled||urgent&&urgencyEnabled)?'P2 · Повышенный':'P3 · Обычный',response:sla?.response||'Не определён',resolution:sla?.resolution||'Не определён',approval:approval?.name||'Не определено',reason:big?'Сообщённый масштаб: весь отдел':'По ответам сотрудника'};
}
export function createSession(d,entryId){
  const entry=d.entries.find(e=>e.id===entryId);
  if(!entry||!block(d,entry.start)) throw new Error('Точка входа недоступна');
  return settleVisibility(d,{entryId,reportedSymptom:entry.title,current:entry.start,answers:{},verifiedFacts:[],history:[entry.start],diagnostics:[],state:'active',error:'',ticket:null});
}
export function advance(d,s,value,diagnosticOutcome='unavailable'){
  if(s.state!=='active')return s;
  const current=block(d,s.current);
  if(!current)return {...s,error:'Этот шаг недоступен. Вернитесь в каталог.'};
  const next=clone(s);next.error='';
  if(current.kind==='question'){
    if(!current.choices?.includes(value)&&!(value===''&&!current.required))return {...s,error:'Выберите вариант ответа. Можно выбрать «Не знаю».'};
    if(value!=='')next.answers[current.id]=value;
  }
  if(current.kind==='diagnostic'){
    if(!['unavailable','denied','timeout','capability_absent'].includes(diagnosticOutcome))return {...s,error:'Результат диагностики не поддерживается.'};
    const inputs=Object.fromEntries(d.blocks.filter(b=>b.kind==='question'&&b.influences?.includes('diagnostic')&&s.answers[b.id]!==undefined).map(b=>[b.title,s.answers[b.id]]));
    next.diagnostics.push({block:current.id,status:diagnosticOutcome,simulated:true,consentRequired:!!current.consent,inputs});
  }
  if(current.kind==='decision'&&!['yes','no','unknown'].includes(value))return {...s,error:'Укажите, восстановилась ли печать.'};
  const edge=d.edges.find(e=>e.source===current.id&&(current.kind!=='decision'||e.when===(value==='yes'?'yes':'no')));
  if(!edge||!block(d,edge.target))return {...s,error:'Следующий шаг не настроен. Обратитесь к администратору.'};
  next.current=edge.target;next.history.push(edge.target);
  const target=block(d,edge.target);
  if(target.kind==='ticket'&&(!next.answers.impact||!next.answers.urgency))return {...s,error:'Для передачи в поддержку нужны ответы о масштабе и срочности. Вернитесь к вопросам.'};
  if(target.kind==='finish')next.state='solved';
  if(target.kind==='ticket'){next.state='ticket';next.ticket='DEMO-1042';}
  return settleVisibility(d,next);
}
export function supportEscape(d,s){
  // Collect mandatory policy inputs before review; never invent missing answers.
  const id=!s.answers.impact?'impact':!s.answers.urgency?'urgency':'review';
  return {...s,current:id,history:[...s.history,id],supportRequested:true,error:''};
}
export function nextSession(d,s,value,outcome){
  let next=advance(d,s,value,outcome);
  if(s.supportRequested&&!next.error&&s.current==='urgency')next={...next,current:'review',history:[...next.history,'review']};
  return next;
}
export function runPath(d,entryId,result='no',impact='Только я',urgency='Можно подождать',outcome='unavailable'){
  let s=createSession(d,entryId);
  for(let i=0;i<40&&s.state==='active';i++){
    const b=block(d,s.current);
    const value=b.id==='impact'?impact:b.id==='urgency'?urgency:b.kind==='question'?b.choices?.[0]:b.kind==='decision'?result:'ack';
    s=nextSession(d,s,value,outcome);
    if(s.error)break;
  }
  return s;
}
export function issues(d){
  const out=[];
  for(const e of d.entries){if(!e.title.trim())out.push({entry:e.id,message:'У пункта каталога нет названия',screen:'entries'});if(!block(d,e.start))out.push({entry:e.id,message:`«${e.title}»: начальный шаг недоступен`,screen:'entries'});if(!d.categories.some(c=>c.id===e.category))out.push({entry:e.id,message:`«${e.title}»: категория недоступна`,screen:'entries'});}
  for(const b of d.blocks){if(!b.title.trim())out.push({block:b.id,message:'У блока нет названия',screen:'settings'});if(b.kind==='question'&&(!b.choices?.length||b.choices.some(x=>!x.trim())))out.push({block:b.id,message:`«${b.title}»: заполните варианты ответа`,screen:'settings'});}
  for(const id of ['impact','urgency']){const b=block(d,id);if(b&&!b.required)out.push({block:id,message:`«${b.title}»: ответ обязателен для обработки обращения`,screen:'settings'});}
  for(const [kind,id] of Object.entries(d.policies)){if(!policyLibrary[kind].some(p=>p.id===id))out.push({message:'Выбранная политика недоступна',screen:'processing'});}
  for(const e of d.entries){if(!block(d,e.start))continue;try{for(const result of ['yes','no','unknown']){const s=runPath(d,e.id,result);if(s.error||s.state==='active')out.push({entry:e.id,message:`«${e.title}»: маршрут не завершён`,screen:'builder'});if(s.state==='ticket'&&(!s.answers.impact||!s.answers.urgency))out.push({entry:e.id,message:`«${e.title}»: отсутствуют обязательные ответы для обработки`,screen:'builder'});}}catch{out.push({entry:e.id,message:`«${e.title}»: повреждён маршрут`,screen:'builder'});}}
  return [...new Map(out.map(issue=>[`${issue.screen}:${issue.entry||issue.block||''}:${issue.message}`,issue])).values()];
}
export function runAll(d){
  const failures=issues(d);let paths=0;
  if(!failures.length)for(const e of d.entries)for(const answer of block(d,'impact').choices)for(const urgency of block(d,'urgency').choices)for(const result of ['yes','no','unknown'])for(const outcome of ['unavailable','denied','timeout','capability_absent']){
    const s=runPath(d,e.id,result,answer,urgency,outcome);paths++;if(s.error||s.state==='active')failures.push({message:`Маршрут «${e.title}» не завершён`,screen:'builder'});
  }
  return {fingerprint:fingerprint(d),paths,failures,entries:d.entries.map(e=>e.id)};
}
export function ready(d){return !!d.testReceipt&&d.testReceipt.fingerprint===fingerprint(d)&&!d.testReceipt.failures.length&&!issues(d).length;}
export function publish(d,comment){
  if(!ready(d))throw new Error('Проверка не выполнена или устарела. Проверьте текущий черновик.');
  if(!comment.trim())throw new Error('Добавьте описание изменений.');
  const next=clone(d),version=Math.max(...d.versions.map(v=>v.version))+1;
  next.entries=next.entries.map(e=>({...e,status:'published'}));
  next.versions.unshift({version,date:'13.10.2026',comment:comment.trim(),snapshot:snapshot(next)});
  next.testReceipt=null;return next;
}
