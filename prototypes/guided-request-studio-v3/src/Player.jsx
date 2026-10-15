import {useState,useEffect} from 'react';
import {ArrowLeft,ArrowRight,CheckCircle2,LifeBuoy,Printer,RotateCcw,ShieldCheck,Ticket,User,FlaskConical} from 'lucide-react';
import {block,createSession,nextSession,processing,supportEscape} from './model';
import {Button,Notice,Tag,KeyValue,NextLink} from './ui';

export function Player({data,entryId,compact=false,simulation=true,outcome='unavailable',onSession,onCatalog,onDone,initialSession}){
  const [session,setSession]=useState(()=>initialSession||createSession(data,entryId));
  const [answer,setAnswer]=useState('');const [comment,setComment]=useState('');
  const b=block(data,session.current),p=processing(data,session.answers);
  const update=next=>{setSession(next);setAnswer('');onSession?.(next);};
  const next=value=>update(nextSession(data,session,value,outcome));
  const title=data.entries.find(e=>e.id===entryId)?.title||'Проблемы с печатью';
  if(!b)return <Notice tone="error">Шаг недоступен. Вернитесь в каталог.</Notice>;
  return <div className={`player ${compact?'compact':''}`} data-testid="scenario-player">
    <div className="player-top"><button className="text-link" onClick={onCatalog||(()=>update(createSession(data,entryId)))}><ArrowLeft size={16}/>{onCatalog?'Каталог':'Начать заново'}</button><Tag tone="neutral">{simulation?'Предпросмотр':'Демо'}</Tag></div>
    <div className="player-title"><span className="icon-tile green"><Printer size={22}/></span><h2>{title}</h2></div>
    <div className="step-line"><span>Помощь с печатью</span><span>{session.state==='active'?`Шаг ${session.history.length}`:'Завершено'}</span></div>
    <div className="progress"><span style={{width:session.state!=='active'?'100%':`${Math.min(90,session.history.length*14)}%`}}/></div>
    {session.state==='solved'?<div className="outcome"><CheckCircle2 size={44}/><h2>Печать снова работает</h2><p>{b.message||'Рады, что удалось решить проблему.'}</p><Notice>Вы сообщили, что проблема решена. Обращение в поддержку не создано.</Notice><Button primary onClick={onDone||(()=>update(createSession(data,entryId)))}>Вернуться в каталог</Button></div>
      :session.state==='ticket'?<div className="outcome"><Ticket size={44}/><h2>Передано в поддержку</h2><p>Демонстрационное обращение <strong>{session.ticket}</strong></p><KeyValue label="Команда" value={p.queue}/><KeyValue label="Ответ" value={p.response}/><Notice>Это результат локального прототипа. Реальная заявка не отправлялась.</Notice><Button primary onClick={onDone||(()=>update(createSession(data,entryId)))}>Вернуться в каталог</Button></div>
      :<>
        <div className="step-heading"><span className="eyebrow">{b.kind==='question'?'Уточним проблему':b.kind==='instruction'?'Попробуйте сами':b.kind==='diagnostic'?'Проверка':b.kind==='review'?'Передача в поддержку':'Проверим результат'}</span><h3>{b.title}</h3></div>
        {b.hint&&<p className="section-intro">{b.hint}</p>}
        {b.kind==='question'&&<div className="radio-options">{b.choices.map((option,i)=><label className={`radio-row ${answer===option?'chosen':''}`} key={`${i}-${option}`}><input type="radio" name={`answer-${entryId}`} checked={answer===option} onChange={()=>setAnswer(option)}/><span>{option||'Без названия'}</span></label>)}</div>}
        {b.kind==='instruction'&&<><p className="instruction-copy">{b.body}</p><label className="checkbox-row"><input type="checkbox" checked={answer==='ack'} onChange={e=>setAnswer(e.target.checked?'ack':'')}/>Я выполнил рекомендации</label></>}
        {b.kind==='diagnostic'&&<><div className="diagnostic-state"><ShieldCheck size={30}/><strong>Автоматическая проверка недоступна</strong><p>{outcome==='timeout'?'Время ожидания истекло.':outcome==='denied'?'Разрешение на проверку не получено.':outcome==='capability_absent'?'Устройство не поддерживает эту проверку.':'Продолжим с ручной проверкой результата.'}</p></div><Notice>Проверенных данных о принтере пока нет.</Notice></>}
        {b.kind==='decision'&&<div className="radio-options">{[['yes','Да, печать работает'],['no','Нет, проблема осталась'],['unknown','Не знаю']].map(([value,label])=><label className={`radio-row ${answer===value?'chosen':''}`} key={value}><input type="radio" name="resolution" checked={answer===value} onChange={()=>setAnswer(value)}/><span>{label}</span></label>)}</div>}
        {b.kind==='review'&&<><div className="review-summary"><KeyValue label="Вы сообщили" value={session.reportedSymptom}/><KeyValue label="Масштаб" value={session.answers.impact||'Не указан'}/><KeyValue label="Срочность" value={session.answers.urgency||'Не указана'}/><KeyValue label="Команда" value={p.queue}/><KeyValue label="Ожидаемый ответ" value={p.response}/><KeyValue label="Согласование" value={p.approval}/></div><label className="field"><span>Комментарий для поддержки</span><textarea rows={3} value={comment} onChange={e=>setComment(e.target.value)} placeholder="Дополнительные подробности, если нужно"/></label><Notice>Автоматическая диагностика не подтвердила причину. Передадим ваши ответы и пройденные шаги.</Notice></>}
        {session.error&&<p className="field-error" role="alert">{session.error}</p>}
        <Button primary className="player-next" icon={ArrowRight} onClick={()=>next(b.kind==='question'||b.kind==='decision'?answer:'ack')} disabled={b.kind==='instruction'&&answer!=='ack'}>{b.kind==='review'?'Передать в поддержку':b.kind==='diagnostic'?'Продолжить вручную':'Далее'}</Button>
        {b.kind==='instruction'&&<button className="support-escape" onClick={()=>update(supportEscape(data,session))}><LifeBuoy size={16}/>Нужна помощь специалиста</button>}
      </>}
    {simulation&&<div className="preview-context"><details><summary><User size={16}/>Ответы сотрудника</summary>{Object.keys(session.answers).length?<div>{Object.entries(session.answers).map(([key,value])=><KeyValue key={key} label={block(data,key)?.title||key} value={value}/>)}</div>:<p>Ответов пока нет</p>}</details>{session.diagnostics.some(x=>Object.keys(x.inputs||{}).length>0)&&<details><summary><ShieldCheck size={16}/>Входные данные для диагностики</summary>{session.diagnostics.flatMap(x=>Object.entries(x.inputs||{})).map(([label,value])=><KeyValue key={label} label={label} value={value}/>)}<p>Проверка недоступна. Эти ответы не являются подтверждёнными фактами.</p></details>}<details><summary><ShieldCheck size={16}/>Проверенные факты: {session.verifiedFacts.length||'пока нет'}</summary><p>Сообщённый симптом и ответы остаются словами сотрудника. Причина не подтверждена диагностикой.</p></details><div className="demo-note"><FlaskConical size={16}/>Локальная симуляция · без реальных заявок</div></div>}
  </div>;
}
export function PreviewPane({data,entryId,setEntry,onCatalog}){
  const [mode,setMode]=useState('answer'),[s,setS]=useState(null);
  const entry=data.entries.find(e=>e.id===entryId);
  const previewKey=`${entryId}:${entry?.start}:${entry?.title}`;
  useEffect(()=>setS(null),[previewKey]);
  return <aside className="preview-pane"><header><h3>Глазами сотрудника</h3><Tag tone="blue">Предпросмотр</Tag></header><label className="field slim"><span className="visually-hidden">Пункт каталога</span><select aria-label="Пункт каталога" value={entryId} onChange={e=>{setEntry(e.target.value);setS(null);}}>{data.entries.map(e=><option key={e.id} value={e.id}>{e.title}</option>)}</select></label><div className="segments"><button className={mode==='answer'?'active':''} onClick={()=>setMode('answer')}>Ответить</button><button className={mode==='route'?'active':''} onClick={()=>setMode('route')}>Маршрут</button></div>{mode==='answer'?<Player key={previewKey} data={data} entryId={entryId} compact onSession={setS} onCatalog={onCatalog}/>:<div className="trace"><h3>Пройденные шаги</h3>{(s?.history||[data.entries.find(e=>e.id===entryId)?.start]).map((id,i)=><div className="trace-step" key={`${id}-${i}`}><span>{i+1}</span><div><strong>{block(data,id)?.title}</strong><small>{s?.answers[id]||''}</small></div></div>)}<Notice>Это маршрут текущего предпросмотра.</Notice></div>}</aside>;
}
