import { RequestFormFieldControl, type DynamicFormValues } from "./dynamic-form";
import { ScenarioFields, type ScenarioProjectedField } from "./scenario-fields";
import { Button } from "./ui/form-controls";
export type ScenarioStepDisplay = {
 id: string; kind: string; title: string;
 fields?: (ScenarioProjectedField & { value?: DynamicFormValues[string]; allow_unknown?: boolean })[];
 layout?: "single" | "group" | "section"; has_dynamic_fields?: boolean;
 content?: { body: string; format: string }; acknowledgment_required?: boolean; can_request_ticket?: boolean; message?: string;
 answers?: { key: string; label: string; type: string; value: unknown; display_value: string }[];
};
/** Shared employee step content. Effects and lifecycle commands belong to the caller. */
export function ScenarioStepContent({ block, values, errors, acknowledged, onValue, onAcknowledged, onRequestTicket }: {
 block: ScenarioStepDisplay; values: DynamicFormValues; errors?: Record<string,string>; acknowledged: boolean;
 onValue: (key: string, value: DynamicFormValues[string]) => void; onAcknowledged: (value: boolean) => void; onRequestTicket?: () => void;
}) {
 return <>
  <ScenarioFields fields={block.fields || []} layout={block.layout} renderField={field => <>
   <RequestFormFieldControl field={field} value={values[field.key]} error={errors?.[field.key]} onChange={value=>onValue(field.key,value)} />
   {field.allow_unknown && <label className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={values[field.key]===null} onChange={event=>onValue(field.key,event.currentTarget.checked?null:undefined)} />Не знаю</label>}
  </>} />
  {block.content && <p className="whitespace-pre-wrap break-words">{block.content.body}</p>}
  {block.kind==="instruction" && <label className="flex gap-2"><input type="checkbox" checked={acknowledged} onChange={event=>onAcknowledged(event.target.checked)} />Инструкция выполнена</label>}
  {block.kind==="instruction" && block.can_request_ticket && <Button type="button" variant="outline" disabled={!onRequestTicket} onClick={onRequestTicket}>Нужна помощь поддержки</Button>}
  {block.answers && <dl className="grid gap-3">{block.answers.map(item=><div key={item.key}><dt className="font-medium">{item.label}</dt><dd className="break-words text-sm">{item.display_value}</dd></div>)}</dl>}
  {block.message && <p>{block.message}</p>}
 </>;
}
