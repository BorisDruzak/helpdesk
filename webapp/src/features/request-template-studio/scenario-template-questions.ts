import { fieldLabels, newBlock, newKey, roleLabels } from "./scenario-builder-model";
import type { ScenarioDraftDefinition, ScenarioField, ScenarioFieldType, ScenarioRole } from "./scenario-contract";
import { positionBlock, requireAcyclic, stableMapPositions } from "./scenario-map-model";

type TemplateField = { key: string; label: string; type: string; required: boolean; options?: unknown[]; visible_when?: unknown; validation?: Record<string, unknown>; process_mapping?: Record<string, unknown> };
export function addTemplateQuestions(definition: ScenarioDraftDefinition, target: string, canonical: TemplateField[]): ScenarioDraftDefinition {
  const result = definition.blocks?.find(block=>block.id===target);
  if(result?.kind!=="submit_ticket")throw new Error("Выберите результат «Создать обращение».");
  const required=canonical.filter(field=>field.required);
  if(!required.length)throw new Error("В шаблоне нет обязательных вопросов. Проверьте остальные настройки обработки.");
  if(required.length>64||(definition.blocks?.length??0)>=256)throw new Error("Достигнут лимит вопросов или блоков карты.");
  const incoming=definition.blocks?.filter(block=>block.transitions?.some(edge=>edge.to===target))??[];
  if(incoming.length===1&&incoming[0].kind==="form_page"&&required.every(field=>incoming[0].kind==="form_page"&&incoming[0].fields.some(item=>(item.process_mapping?.fact_key??item.key)===field.key&&item.required)))return definition;
  const fields:ScenarioField[]=required.map(field=>{
    if(!(field.type in fieldLabels)||field.visible_when)throw new Error("Этот шаблон содержит специальные или условные вопросы. Настройте их через редактор формы.");
    if(Object.keys(field.validation??{}).some(key=>!["min_length","max_length","min_value","max_value"].includes(key)))throw new Error("В шаблоне есть специальные проверки ответа. Настройте их через редактор формы.");
    const roles=field.process_mapping?.roles;
    if(Array.isArray(roles)&&roles.some(role=>!(String(role) in roleLabels)))throw new Error("В шаблоне есть неподдерживаемое назначение ответа. Проверьте шаблон формы.");
    return {key:newKey("field"),label:field.label,type:field.type as ScenarioFieldType,required:true,options:(field.options??[]).map(option=>{const item=option as {value:unknown;label:unknown};if(typeof item.value!=="string"||typeof item.label!=="string")throw new Error("Проверьте варианты ответов в шаблоне.");return {value:item.value,label:item.label};}),validation:field.validation as ScenarioField["validation"],process_mapping:{roles:Array.isArray(roles)?roles as ScenarioRole[]:[],fact_key:field.key}};
  });
  const base=newBlock("form_page");
  const page={...base,kind:"form_page" as const,title:"Данные для обращения",fields,transitions:[{to:target}]};
  const next={...definition,entry_block_id:definition.entry_block_id===target?page.id:definition.entry_block_id,entry_points:definition.entry_points?.map(entry=>entry.target_block_id===target?{...entry,target_block_id:page.id}:entry),blocks:[...(definition.blocks??[]).map(block=>({...block,transitions:block.transitions?.map(edge=>edge.to===target?{...edge,to:page.id}:edge)})),page]};
  const origin=stableMapPositions(definition)[target];
  return requireAcyclic(positionBlock(next,page.id,{x:origin.x+310,y:origin.y}));
}
