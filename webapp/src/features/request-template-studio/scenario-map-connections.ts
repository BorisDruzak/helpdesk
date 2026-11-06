import type { ScenarioBlock,ScenarioDraftDefinition } from "./scenario-contract";
import type { ConnectionDrop } from "./scenario-connection-menu";
import { addMapBlock,connectBlocks,insertOnTransition,reconnectStart } from "./scenario-map-model";
import { beginCatalogEntrance,completeCatalogEntrance,pendingCatalogEntrances } from "./scenario-pending-entrances";
import { connectPolicyAttachment,isPolicyAttachment } from "./scenario-policy-attachments-model";
import { answerBranchChoices,connectAnswerBranch,defaultAnswerBranchField } from "./scenario-answer-branches";
export function addConnectedMapBlock(d:ScenarioDraftDefinition,drop:ConnectionDrop,kind:ScenarioBlock["kind"]|"catalog_entrance",position:{x:number;y:number},answerField?:string):ScenarioDraftDefinition{
 if(drop.type==="source"&&drop.source==="studio:metadata"){
  if(kind!=="catalog_entrance")throw new Error("От «Начала» добавляется вход из каталога.");
  return beginCatalogEntrance(d,drop.source,position);
 }
 if(kind==="catalog_entrance")throw new Error("Вход создаётся только от «Начала».");
 if(drop.type==="route")return insertOnTransition(d,drop.source,drop.index,kind,position);
 if(drop.type==="source"&&drop.handle?.startsWith("route-"))return insertOnTransition(d,drop.source,Number(drop.handle.slice(6)),kind,position);
 let next=addMapBlock(d,kind,position);const target=next.blocks!.at(-1)!.id;
 if(drop.type==="entrance")return drop.key&&pendingCatalogEntrances(d).some(e=>e.key===drop.key)?completeCatalogEntrance(next,drop.key,target):reconnectStart(next,drop.key,target);
 if(isPolicyAttachment(d.blocks?.find(b=>b.id===drop.source)))return connectPolicyAttachment(next,drop.source,target);
 if(drop.handle?.startsWith("answer-")){
  const field=defaultAnswerBranchField(d,drop.source,answerField),choice=field&&answerBranchChoices(field)[Number(drop.handle.slice(7))];
  if(!choice)throw new Error("Выберите доступный ответ связанного вопроса.");
  return connectAnswerBranch(next,drop.source,target,choice.when);
 }
 next=connectBlocks(next,drop.source,target);return next;
}
