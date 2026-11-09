import type { ScenarioBlock, ScenarioDraftDefinition } from "./scenario-contract";

export type PolicyAttachmentBlock = Extract<ScenarioBlock, { kind: "sla_attachment" | "ola_attachment" | "routing_attachment" }>;
export function isPolicyAttachment(block: ScenarioBlock | ScenarioBlock["kind"] | undefined): block is PolicyAttachmentBlock {
 const kind = typeof block === "string" ? block : block?.kind;
 return kind === "ola_attachment" || kind === "sla_attachment" || kind === "routing_attachment";
}
export function policyAttachmentsFor(definition: ScenarioDraftDefinition, target: string): PolicyAttachmentBlock[] {
 return (definition.blocks ?? []).filter((block): block is PolicyAttachmentBlock => isPolicyAttachment(block) && block.attached_to === target);
}
/** Settings links never mutate transitions or start references. Reconnection is atomic. */
export function connectPolicyAttachment(definition: ScenarioDraftDefinition, attachmentId: string, targetId: string): ScenarioDraftDefinition {
 if (definition.schema_version !== 4) throw new Error("Прикреплённые настройки доступны в версии 4 карты");
 const attachment = definition.blocks?.find(block => block.id === attachmentId);
 const target = definition.blocks?.find(block => block.id === targetId);
 if (!attachment || !isPolicyAttachment(attachment)) throw new Error("Выберите карточку настройки SLA, OLA или маршрута");
 if (!target) throw new Error("Выберите существующий блок для настройки");
 if (isPolicyAttachment(target)) throw new Error("Нельзя прикрепить настройку к другой настройке. Выберите шаг или результат.");
 if (policyAttachmentsFor(definition, targetId).some(block => block.kind === attachment.kind && block.id !== attachmentId)) throw new Error(`У блока «${target.title}» уже есть настройка ${attachment.kind === "sla_attachment" ? "SLA" : attachment.kind === "ola_attachment" ? "OLA" : "маршрута"}. Сначала отсоедините её.`);
 return { ...definition, blocks: definition.blocks?.map(block => block.id === attachmentId ? { ...attachment, attached_to: targetId } : block) };
}
export function detachPolicyAttachment(definition: ScenarioDraftDefinition, attachmentId: string): ScenarioDraftDefinition {
 return { ...definition, blocks: definition.blocks?.map(block => {
  if (block.id !== attachmentId || !isPolicyAttachment(block)) return block;
  const next = { ...block }; delete next.attached_to; return next;
 }) };
}
/** A deleted target keeps editable settings drafts, or redirects them after conflict validation. */
export function reassignPolicyAttachments(definition: ScenarioDraftDefinition, oldTarget: string, replacement: string | null): ScenarioDraftDefinition {
 let next = definition;
 for (const block of policyAttachmentsFor(definition, oldTarget)) next = replacement
  ? connectPolicyAttachment(next, block.id, replacement)
  : detachPolicyAttachment(next, block.id);
 return next;
}
