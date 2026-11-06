import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScenarioEmployeePreview } from "./scenario-employee-preview";
import { ScenarioPagePreview } from "./scenario-requester-preview";
import { ScenarioApiError, simulateScenario, type ScenarioDetail, type ScenarioSimulation } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";
vi.mock("./scenario-api",async importOriginal=>({...await importOriginal<typeof import('./scenario-api')>(),simulateScenario:vi.fn()}));
afterEach(()=>vi.clearAllMocks());
const definition={schema_version:4,execution_semantics:3,scenario_key:'preview',title:'Проверка',entry_block_id:'q',blocks:[{id:'q',kind:'form_page',title:'Выбор',fields:[{key:'name',type:'text',label:'Имя'}]}],process_binding:{request_template_key:'request'}} as ScenarioDraftDefinition;
const detail={scenario:{id:'s'},draft:{revision:1,definition}} as ScenarioDetail;
const response=(id='q',extra:Partial<ScenarioSimulation>={}):ScenarioSimulation=>({revision:1,state:{current_block_id:id,revision:id==='q'?1:2,answers:{},history:id==='q'?[]:['q'],results:{},state:'active'},current_block:{id,kind:'form_page',title:id},current_step:id==='q'?{id,kind:'form_page',title:'Выбор',fields:[{key:'name',type:'text',label:'Имя',required:true}],actions:[{key:'one',label:'Первый путь'},{key:'two',label:'Второй путь'}]}:{id,kind:'instruction',title:id,content:{body:'Описание',format:'plain'}},...extra} as ScenarioSimulation);
it('starts automatically and directly follows distinct buttons then replays back',async()=>{
 vi.mocked(simulateScenario).mockImplementation(async(_id,_revision,steps=[])=>response(steps.at(-1)?.action_key==='one'?'Первый':steps.length?'Второй':'q'));
 const prepare=vi.fn(async()=>detail);render(<ScenarioEmployeePreview definition={definition} ensureSaved={prepare}/>);
 expect(await screen.findByRole('textbox',{name:/Имя/})).toBeVisible();expect(screen.queryByRole('button',{name:'Начать проверку'})).not.toBeInTheDocument();
 fireEvent.change(screen.getByRole('textbox',{name:/Имя/}),{target:{value:'Тест'}});fireEvent.click(screen.getByRole('button',{name:'Первый путь'}));
 expect(await screen.findByRole('heading',{name:'Первый'})).toBeVisible();
 expect(vi.mocked(simulateScenario).mock.lastCall?.[2]).toEqual([{expected_block_id:'q',revision:1,answers:{name:'Тест'},action_key:'one'}]);
 fireEvent.click(screen.getByRole('button',{name:'Назад'}));expect(await screen.findByRole('button',{name:'Второй путь'})).toBeVisible();
 expect(vi.mocked(simulateScenario).mock.lastCall?.[2]).toEqual([]);
 fireEvent.click(screen.getByRole('button',{name:'Второй путь'}));expect(await screen.findByRole('heading',{name:'Второй'})).toBeVisible();
 expect(vi.mocked(simulateScenario).mock.lastCall?.[6]).toBe(true);expect(prepare).toHaveBeenCalledTimes(1);
});
it('shows canonical field errors next to the employee answer',async()=>{
 vi.mocked(simulateScenario).mockResolvedValueOnce(response()).mockRejectedValueOnce(new ScenarioApiError(400,'INVALID_ANSWERS',[],[],{name:'Field is required'}));
 render(<ScenarioEmployeePreview definition={definition} ensureSaved={async()=>detail}/>);
 fireEvent.click(await screen.findByRole('button',{name:'Первый путь'}));
 expect(await screen.findByText('Ответьте на вопрос.')).toBeVisible();expect(screen.getByRole('textbox',{name:/Имя/})).toHaveAttribute('aria-invalid','true');
});
it('explains an unfinished leaf without inventing a final result',async()=>{
 vi.mocked(simulateScenario).mockResolvedValue(response('Лист',{preview_stop:{code:'missing_continuation',block_id:'Лист'}}));
 render(<ScenarioEmployeePreview definition={definition} ensureSaved={async()=>detail}/>);
 expect(await screen.findByText(/Следующий шаг ещё не настроен/)).toBeVisible();
 expect(screen.queryByRole('button',{name:'Продолжить'})).not.toBeInTheDocument();expect(screen.queryByText(/Результат серверной проверки/)).not.toBeInTheDocument();
});
it('does not prepare or simulate an empty draft',()=>{
 const ensureSaved=vi.fn();render(<ScenarioEmployeePreview definition={{...definition,blocks:[],entry_block_id:null}} ensureSaved={ensureSaved}/>);
 expect(screen.getByText(/Добавьте первый блок/)).toBeVisible();expect(ensureSaved).not.toHaveBeenCalled();expect(simulateScenario).not.toHaveBeenCalled();
});
it('ignores stale asynchronous results after the definition changes',async()=>{
 let first!:(value:ScenarioSimulation)=>void;
 vi.mocked(simulateScenario).mockImplementationOnce(()=>new Promise(resolve=>{first=resolve;})).mockResolvedValueOnce(response('Актуальный'));
 const view=render(<ScenarioEmployeePreview definition={definition} ensureSaved={async()=>detail}/>);
 await waitFor(()=>expect(simulateScenario).toHaveBeenCalledTimes(1));
 view.rerender(<ScenarioEmployeePreview definition={{...definition,title:'Изменено'}} ensureSaved={async()=>detail}/>);
 expect(await screen.findByRole('heading',{name:'Актуальный'})).toBeVisible();first(response('Устаревший'));
 await waitFor(()=>expect(screen.queryByRole('heading',{name:'Устаревший'})).not.toBeInTheDocument());
});
it('previews conditional visibility with the current uncommitted answers',async()=>{
 const initial=response();initial.current_step={id:'q',kind:'form_page',title:'Выбор',has_dynamic_fields:true,fields:[{key:'show',type:'checkbox',label:'Показать деталь?'}]};
 const revealed=response();revealed.current_step={...initial.current_step,fields:[...initial.current_step.fields!,{key:'detail',type:'text',label:'Деталь',required:true}]};
 vi.mocked(simulateScenario).mockResolvedValueOnce(initial).mockResolvedValueOnce(revealed);
 render(<ScenarioEmployeePreview definition={definition} ensureSaved={async()=>detail}/>);
 fireEvent.click(await screen.findByRole('checkbox',{name:/Показать деталь/}));
 expect(await screen.findByRole('textbox',{name:/Деталь/})).toBeVisible();
 expect(vi.mocked(simulateScenario).mock.lastCall?.[2]).toEqual([]);
 expect(vi.mocked(simulateScenario).mock.lastCall?.[3]).toMatchObject({expected_block_id:'q',revision:1,answers:{show:true}});
});
it('does not request simulation for identity preparation from an abandoned definition',async()=>{
 let release!:(value:ScenarioDetail)=>void;
 const prepare=vi.fn().mockImplementationOnce(()=>new Promise(resolve=>{release=resolve;})).mockResolvedValueOnce(detail);
 vi.mocked(simulateScenario).mockResolvedValueOnce(response('Новая карта'));
 const view=render(<ScenarioEmployeePreview definition={definition} ensureSaved={prepare}/>);
 view.rerender(<ScenarioEmployeePreview definition={{...definition,scenario_key:'different'}} ensureSaved={prepare}/>);
 expect(await screen.findByRole('heading',{name:'Новая карта'})).toBeVisible();release(detail);
 await waitFor(()=>expect(simulateScenario).toHaveBeenCalledTimes(1));
});
it('keeps archived maps as appearance-only without attempting a save or new execution',()=>{
 const prepare=vi.fn();render(<ScenarioPagePreview definition={definition} detail={{...detail,scenario:{...detail.scenario,archived:true}}} ensureSaved={prepare} offeringTitle="Архив" onClose={vi.fn()}/>);
 expect(screen.getByRole('button',{name:'Продолжить'})).toBeDisabled();expect(prepare).not.toHaveBeenCalled();expect(simulateScenario).not.toHaveBeenCalled();
});
it('selects a single enabled named entrance and can return to the primary entrance',async()=>{
 const alternate={...definition,entry_points:[{key:'special',title:'Особый вход',target_block_id:'alternate',enabled:true}],blocks:[...definition.blocks!,{id:'alternate',kind:'instruction',title:'Особый шаг',content:{body:'Другой вход'}}]} as ScenarioDraftDefinition;
 vi.mocked(simulateScenario).mockImplementation(async(_id,_revision,_steps,_preview,_outcomes,entry)=>response(entry==='special'?'Особый шаг':'q'));
 render(<ScenarioEmployeePreview definition={alternate} ensureSaved={async()=>({...detail,draft:{...detail.draft,definition:alternate}})}/>);
 expect(await screen.findByRole('heading',{name:'Выбор'})).toBeVisible();
 const chooser=screen.getByRole('combobox',{name:'Вход из каталога'});
 fireEvent.change(chooser,{target:{value:'special'}});
 expect(await screen.findByRole('heading',{name:'Особый шаг'})).toBeVisible();
 expect(vi.mocked(simulateScenario).mock.lastCall?.[5]).toBe('special');
 fireEvent.change(chooser,{target:{value:''}});
 expect(await screen.findByRole('heading',{name:'Выбор'})).toBeVisible();
 expect(vi.mocked(simulateScenario).mock.lastCall?.[5]).toBe('');
});
