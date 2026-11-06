import { createContext, useContext, useRef, type ReactNode } from "react";
import { ScenarioAttachmentEditor } from "../requester/scenario-attachments";
import type { ScenarioAttachment, ScenarioDraftDefinition, ScenarioRichDocument, ScenarioRichNode } from "./scenario-contract";
import { uploadScenarioAttachment, type ScenarioDetail } from "./scenario-api";

type Context = { id?: string; definition: ScenarioDraftDefinition; getDefinition?: () => ScenarioDraftDefinition | null; ensureSaved?: () => Promise<ScenarioDetail>; change: (definition: ScenarioDraftDefinition) => void };
const AuthorAttachments = createContext<Context | null>(null);
export function ScenarioAuthorAttachmentProvider({ id, definition, onChange, ensureSaved, getDefinition, children }: { id?: string; definition: ScenarioDraftDefinition; onChange: Context["change"]; ensureSaved?: Context["ensureSaved"]; getDefinition?: Context["getDefinition"]; children: ReactNode }) {
  const latest = useRef({ id, definition, onChange }); latest.current = { id, definition, onChange };
  return <AuthorAttachments.Provider value={{ id, definition, ensureSaved, getDefinition, change: next => { latest.current.definition = next; latest.current.onChange(next); } }}>{children}</AuthorAttachments.Provider>;
}
function removeRichImage(document: ScenarioRichDocument | null | undefined, assetId: string) {
  if (!document) return document;
  const clean = (nodes: ScenarioRichNode[]): ScenarioRichNode[] => nodes.filter(node => node.type !== "image" || node.attrs?.asset_id !== assetId).map(node => node.content ? { ...node, content: clean(node.content) } : node);
  return { ...document, content: clean(document.content) };
}
export function ScenarioAuthorAttachments({ blockId, fieldKey, attachments, disabled, children }: { blockId: string; fieldKey?: string; attachments?: ScenarioAttachment[]; disabled?: boolean; children?: ReactNode }) {
  const context = useContext(AuthorAttachments);
  const latest = useRef(context); latest.current = context;
  const id = context?.id;
  const scenarioKey = context?.definition.scenario_key;
  function change(transform: (items: ScenarioAttachment[]) => ScenarioAttachment[], removedId?: string) {
    const current = latest.current;
    if (!current || id && current.id !== id) return;
    const definition = current.getDefinition ? current.getDefinition() : current.definition;
    if (!definition || definition.scenario_key !== scenarioKey) return;
    const next = { ...definition, blocks: definition.blocks?.map(block => block.id !== blockId ? block : fieldKey && block.kind === "form_page" ? { ...block, fields: block.fields.map(field => field.key === fieldKey ? { ...field, help_attachments: transform(field.help_attachments || []), ...(removedId ? { help_document: removeRichImage(field.help_document, removedId) } : {}) } : field) } : !fieldKey && block.kind === "instruction" ? { ...block, content: { ...block.content, attachments: transform(block.content.attachments || []), ...(removedId ? { rich_document: removeRichImage(block.content.rich_document, removedId) } : {}) } } : block) };
    current.definition = next; current.change(next);
  }
  return <>
    <ScenarioAttachmentEditor scope={`${scenarioKey || id || "unsaved"}:${blockId}:${fieldKey || "instruction"}`} attachments={attachments} disabled={disabled}
      onUpload={id || context?.ensureSaved ? async (file, signal) => {
        const prepare = latest.current?.ensureSaved;
        const prepared = prepare ? await prepare() : undefined;
        const targetId = prepared?.scenario.id ?? id;
        const current = latest.current;
        if (signal.aborted || !targetId || !current || id && current.id !== id || current.id && current.id !== targetId) return;
        const definition = current.getDefinition ? current.getDefinition() : current.definition;
        if (!definition || definition.scenario_key !== scenarioKey) return;
        const block = definition.blocks?.find(item => item.id === blockId);
        if (!block || (fieldKey ? block.kind !== "form_page" || !block.fields.some(field => field.key === fieldKey) : block.kind !== "instruction")) return;
        const item = await uploadScenarioAttachment(targetId, file, blockId, fieldKey, signal);
        if (!signal.aborted) change(items => [...items, item]);
      } : undefined}
      onRemove={id || context?.ensureSaved ? async assetId => change(items => items.filter(item => item.asset_id !== assetId), assetId) : undefined}>{children}</ScenarioAttachmentEditor>
    {!id && !context?.ensureSaved && <p className="text-sm text-slate-500">Сохраните сценарий, чтобы прикрепить скриншоты и файлы.</p>}
  </>;
}
