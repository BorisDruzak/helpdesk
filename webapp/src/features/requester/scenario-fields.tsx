import type { ReactNode } from "react";
import type { RequestFormField } from "./types";
import type { ScenarioAttachment, ScenarioRichDocument } from "../request-template-studio/scenario-contract";

export type ScenarioProjectedField = RequestFormField & { help_document?: ScenarioRichDocument | null; group?: string | null; group_title?: string | null; help_attachments?: ScenarioAttachment[]; answer_attachments?: ScenarioAttachment[] };
/** Display only: conditions and field validation remain server authoritative. */
export function ScenarioFields<T extends ScenarioProjectedField>({ fields, layout, renderField }: {
  fields: T[]; layout?: "single" | "group" | "section"; renderField: (field: T) => ReactNode;
}) {
  if (layout !== "section") return <>{fields.map(field => <div key={field.key}>{renderField(field)}</div>)}</>;
  const groups = new Map<string, T[]>();
  for (const field of fields) {
    const key = field.group || "";
    const items = groups.get(key) || [];
    items.push(field); groups.set(key, items);
  }
  return <>{[...groups].map(([key, items]) => <fieldset key={key} className="grid min-w-0 gap-4 rounded-lg border border-slate-200 p-4">
    <legend className="px-1 font-semibold">{items.find(field => field.group_title)?.group_title || (key ? "Дополнительные вопросы" : "Общие вопросы")}</legend>
    {items.map(field => <div key={field.key}>{renderField(field)}</div>)}
  </fieldset>)}</>;
}
