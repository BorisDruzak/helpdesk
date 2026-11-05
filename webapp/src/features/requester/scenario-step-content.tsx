import { RequestFormFieldControl, type DynamicFormValues } from "./dynamic-form";
import { ScenarioFields, type ScenarioProjectedField } from "./scenario-fields";
import { Button } from "./ui/form-controls";
import { ScenarioAttachmentEditor, ScenarioAttachments } from "./scenario-attachments";
import type { ScenarioAttachment } from "../request-template-studio/scenario-contract";
export type ScenarioStepDisplay = {
 id: string; kind: string; title: string;
 fields?: (ScenarioProjectedField & { value?: DynamicFormValues[string]; allow_unknown?: boolean })[];
 layout?: "single" | "group" | "section"; has_dynamic_fields?: boolean;
 content?: { body: string; format: string; attachments?: ScenarioAttachment[] }; acknowledgment_required?: boolean; can_request_ticket?: boolean; message?: string;
 answers?: { key: string; label: string; type: string; value: unknown; display_value: string; answer_attachments?: ScenarioAttachment[] }[];
};
/** Shared employee step content. Effects and lifecycle commands belong to the caller. */
export function ScenarioStepContent({ block, values, errors, acknowledged, onValue, onAcknowledged, onRequestTicket, attachmentScope = "preview", onUpload, onRemove, onAttachmentBusy, attachmentsDisabled }: {
 block: ScenarioStepDisplay; values: DynamicFormValues; errors?: Record<string,string>; acknowledged: boolean;
 onValue: (key: string, value: DynamicFormValues[string]) => void; onAcknowledged: (value: boolean) => void; onRequestTicket?: () => void;
 attachmentScope?: string; attachmentsDisabled?: boolean; onUpload?: (key: string, file: File, signal: AbortSignal) => Promise<void>; onRemove?: (key: string, id: string, signal: AbortSignal) => Promise<void>; onAttachmentBusy?: (key: string, busy: boolean) => void;
}) {
 return <>
  <ScenarioFields fields={block.fields || []} layout={block.layout} renderField={field => <ScenarioAttachmentEditor scope={`${attachmentScope}:${block.id}:${field.key}`} attachments={field.answer_attachments} disabled={attachmentsDisabled} onBusy={busy => onAttachmentBusy?.(field.key, busy)} onUpload={onUpload && ["text", "textarea"].includes(field.type) ? (file, signal) => onUpload(field.key, file, signal) : undefined} onRemove={onRemove ? (id, signal) => onRemove(field.key, id, signal) : undefined}>
   <RequestFormFieldControl field={field} value={values[field.key]} error={errors?.[field.key]} onChange={value=>onValue(field.key,value)} />
   <ScenarioAttachments attachments={field.help_attachments} />
   {field.allow_unknown && <label className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={values[field.key]===null} onChange={event=>onValue(field.key,event.currentTarget.checked?null:undefined)} />Не знаю</label>}
  </ScenarioAttachmentEditor>} />
  {block.content && <p className="whitespace-pre-wrap break-words">{block.content.body}</p>}
  <ScenarioAttachments attachments={block.content?.attachments} />
  {block.kind==="instruction" && <label className="flex gap-2"><input type="checkbox" checked={acknowledged} onChange={event=>onAcknowledged(event.target.checked)} />Инструкция выполнена</label>}
  {block.kind==="instruction" && block.can_request_ticket && <Button type="button" variant="outline" disabled={!onRequestTicket} onClick={onRequestTicket}>Нужна помощь поддержки</Button>}
  {block.answers && <dl className="grid gap-3">{block.answers.map(item=><div key={item.key}><dt className="font-medium">{item.label}</dt><dd className="break-words text-sm">{item.display_value}<ScenarioAttachments attachments={item.answer_attachments} /></dd></div>)}</dl>}
  {block.message && <p>{block.message}</p>}
 </>;
}
