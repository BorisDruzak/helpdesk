import {render,screen,cleanup} from "@testing-library/react";
import {afterEach,expect,it,vi} from "vitest";
import {ScenarioPublicationChecks} from "./scenario-publication-checks";
import type {ScenarioPublicationPreview} from "./scenario-api";
import type {ScenarioDraftDefinition} from "./scenario-contract";
afterEach(cleanup);
const definition:ScenarioDraftDefinition={schema_version:3,scenario_key:'s',title:'Услуга',service_code:'it',offering_full_code:'it.s',process_binding:{request_template_key:'t'}};
const preview=(issues:ScenarioPublicationPreview['readiness']['issues']):ScenarioPublicationPreview=>({revision:1,source_hash:'h',health:{health_status:'ok'},readiness:{can_publish:false,variants_checked:0,issues},outcomes:[],diff:[],confirmation_token:null,expires_at:null});
it('explains route and SLA fallback failures separately with concrete next steps',()=>{
 render(<ScenarioPublicationChecks definition={definition} onIssue={vi.fn()} preview={preview([{code:'processing_default_missing',path:'processing.defaults.route',message:'Выберите существующее значение по умолчанию.'},{code:'processing_default_missing',path:'processing.defaults.sla_profile',message:'Выберите существующее значение по умолчанию.'}])}/>);
 expect(screen.getByText('Не выбрано резервное направление')).toBeInTheDocument();expect(screen.getByText('Не выбран резервный SLA')).toBeInTheDocument();expect(screen.getByText(/Откройте настройки обработки в публикации/)).toBeInTheDocument();expect(screen.getByText(/Пути пока не проверены/)).toBeInTheDocument();expect(screen.queryByText('Выберите существующее значение по умолчанию.')).not.toBeInTheDocument();
});
it('groups ticket visibility rules under processing rather than catalogue availability',()=>{
 render(<ScenarioPublicationChecks definition={definition} preview={preview([{code:'visibility_missing',path:'process_binding.policy_refs.visibility',message:'Не настроена действующая политика видимости.'}])}/>);
 expect(screen.queryByRole('heading',{name:'Каталог и доступность'})).not.toBeInTheDocument();expect(screen.getByRole('heading',{name:'Обработка и сроки'})).toBeInTheDocument();expect(screen.getByText(/какие поля и статусы обращения/)).toBeInTheDocument();
});
it('explains a real unavailable SLA without demanding an extra manual profile',()=>{
 render(<ScenarioPublicationChecks definition={{...definition,schema_version:4}} preview={preview([{code:'sla_unavailable',path:'blocks.end.sla_profile',message:'Одна из ветвей не имеет срока выполнения по действующей политике.'}])}/>);
 expect(screen.getByText('Не удалось рассчитать SLA для пути')).toBeInTheDocument();expect(screen.getByText(/Параметры SLA-блока передаются правилам услуги/)).toBeInTheDocument();expect(screen.queryByText(/Создайте профиль/)).not.toBeInTheDocument();
});
it('retains distinct server paths to the same terminal when explaining SLA failures',()=>{
 const paths=['Для завершения «end» не определён срок SLA. Путь: low → end.','Для завершения «end» не определён срок SLA. Путь: high → end.'];
 render(<ScenarioPublicationChecks definition={{...definition,schema_version:4}} preview={preview(paths.map(message=>({code:'sla_unavailable',path:'blocks.end',message})))}/>);
 for(const message of paths)expect(screen.getByText(message)).toBeInTheDocument();
});

it('explains incomplete result transitions in Russian',()=>{
 render(<ScenarioPublicationChecks preview={preview([{code:'missing_fallback',path:'blocks.check.transitions',message:'Every possible result needs an exit and explicit fallback'}])}/>);
 expect(screen.getByRole('alert')).toHaveTextContent('Не настроены переходы для всех результатов');
 expect(screen.getByText(/Укажите один переход без условия/)).toBeVisible();
 expect(screen.getByText(/вместо него можно явно настроить все три ответа/)).toBeVisible();
 expect(screen.queryByText(/Every possible result/)).not.toBeInTheDocument();
});
