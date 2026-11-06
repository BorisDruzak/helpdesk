import { createContext, useContext, useRef, type ReactNode } from "react";
import { ScenarioAttachmentEditor } from "../requester/scenario-attachments";
import type { ScenarioAttachment, ScenarioDraftDefinition, ScenarioRichDocument, ScenarioRichNode } from "./scenario-contract";
import { uploadScenarioAttachment } from "./scenario-api";

type Context = { id?: string; definition: ScenarioDraftDefinition; change: (definition: ScenarioDraftDefinition) => void };
const AuthorAttachments = createContext<Context | null>(null);
export function ScenarioAuthorAttachmentProvider({ id, definition, onChange, children }: { id?: string; definition: ScenarioDraftDefinition; onChange: Context["change"]; children: ReactNode }) {
  const latest = useRef({ id, definition, onChange }); latest.current = { id, definition, onChange };
  return <AuthorAttachments.Provider value={{ id, definition, change: next => { latest.current.definition = next; latest.current.onChange(next); } }}>{children}</AuthorAttachments.Provider>;
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
  function change(transform: (items: ScenarioAttachment[]) => ScenarioAttachment[], removedId?: string) {
    const current = latest.current;
    if (!current || current.id !== id) return;
    const definition = current.definition;
    const next = { ...definition, blocks: definition.blocks?.map(block => block.id !== blockId ? block : fieldKey && block.kind === "form_page" ? { ...block, fields: block.fields.map(field => field.key === fieldKey ? { ...field, help_attachments: transform(field.help_attachments || []), ...(removedId ? { help_document: removeRichImage(field.help_document, removedId) } : {}) } : field) } : !fieldKey && block.kind === "instruction" ? { ...block, content: { ...block.content, attachments: transform(block.content.attachments || []), ...(removedId ? { rich_document: removeRichImage(block.content.rich_document, removedId) } : {}) } } : block) };
    current.definition = next; current.change(next);
  }
  return <>
    <ScenarioAttachmentEditor scope={`${id || "unsaved"}:${blockId}:${fieldKey || "instruction"}`} attachments={attachments} disabled={disabled}
      onUpload={id ? async (file, signal) => { const item = await uploadScenarioAttachment(id, file, blockId, fieldKey, signal); if (!signal.aborted) change(items => [...items, item]); } : undefined}
      onRemove={id ? async assetId => change(items => items.filter(item => item.asset_id !== assetId), assetId) : undefined}>{children}</ScenarioAttachmentEditor>
    {!id && <p className="text-sm text-slate-500">Сохраните сценарий, чтобы прикрепить скриншоты и файлы.</p>}
  </>;
}
