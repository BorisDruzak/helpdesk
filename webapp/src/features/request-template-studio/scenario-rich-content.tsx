import { createElement, type ReactNode } from "react";
import type { ScenarioAttachment, ScenarioRichDocument, ScenarioRichNode } from "./scenario-contract";
import "./scenario-rich.css";
const nodes = new Set(["paragraph", "heading", "text", "bulletList", "orderedList", "listItem", "blockquote", "hardBreak", "image"]);
export function safeRichLink(value: unknown): value is string { return typeof value === "string" && value.length <= 2048 && /^(https?:\/\/|mailto:)/i.test(value) && !/[\u0000-\u0020\u007f]/.test(value); }
export function canonicalRichDocument(document: ScenarioRichDocument): ScenarioRichDocument {
  let count = 0;
  function clean(node: ScenarioRichNode, depth: number): ScenarioRichNode[] {
    if (++count > 1000 || depth > 16 || !nodes.has(node.type)) return [];
    const next: ScenarioRichNode = { type: node.type };
    if (node.type === "text") { next.text = String(node.text ?? "").slice(0, 10000); if (!next.text) return []; }
    if (node.type === "heading") next.attrs = { level: [1, 2, 3].includes(Number(node.attrs?.level)) ? Number(node.attrs?.level) : 2 };
    if (node.type === "orderedList" && node.attrs?.start != null) next.attrs = { start: Math.max(1, Math.min(10000, Number(node.attrs.start) || 1)) };
    if (node.type === "image") next.attrs = { asset_id: String(node.attrs?.asset_id ?? ""), alt: String(node.attrs?.alt ?? "").slice(0, 500) };
    const marks = (node.marks ?? []).flatMap(mark => mark.type === "link" ? safeRichLink(mark.attrs?.href) ? [{ type: "link", attrs: { href: mark.attrs.href } }] : [] : ["bold", "italic", "strike", "code"].includes(mark.type) ? [{ type: mark.type }] : []);
    if (marks.length) next.marks = marks.slice(0, 5);
    if (node.content?.length && !["text", "image", "hardBreak"].includes(node.type)) next.content = node.content.flatMap(child => clean(child, depth + 1));
    return [next];
  }
  return { type: "doc", content: (document.content ?? []).flatMap(node => clean(node, 1)) };
}
export function plainRichDocument(text: string): ScenarioRichDocument { return { type: "doc", content: text.split(/\r?\n/).map(line => ({ type: "paragraph", ...(line ? { content: [{ type: "text", text: line }] } : {}) })) }; }
export function richPlainText(document: ScenarioRichDocument): string {
  const text = (node: ScenarioRichNode): string => node.type === "text" ? node.text ?? "" : node.type === "image" ? String(node.attrs?.alt ?? "") : (node.content ?? []).map(text).join(node.type === "doc" ? "\n" : "");
  return document.content.map(text).join("\n");
}
export function scopedRichImage(attachments: ScenarioAttachment[], id: unknown) {
  return attachments.find(item => item.asset_id === id && item.url === `/api/web/request-scenario-assets/${encodeURIComponent(item.asset_id)}/download` && /^image\/(png|jpeg|gif|webp)$/i.test(item.mime_type));
}
export function ScenarioRichContent({ document, attachments = [] }: { document: ScenarioRichDocument; attachments?: ScenarioAttachment[] }) {
  const safe = canonicalRichDocument(document);
  function render(node: ScenarioRichNode, key: number): ReactNode {
    if (node.type === "text") {
      let result: ReactNode = node.text;
      for (const mark of node.marks ?? []) result = mark.type === "link" ? <a href={String(mark.attrs!.href)} target="_blank" rel="noopener noreferrer">{result}</a> : createElement(({ bold: "strong", italic: "em", strike: "s", code: "code" } as Record<string, string>)[mark.type], null, result);
      return <span key={key}>{result}</span>;
    }
    if (node.type === "image") { const asset = scopedRichImage(attachments, node.attrs?.asset_id); return asset ? <figure key={key}><img loading="lazy" src={asset.url} alt={String(node.attrs?.alt || asset.name)} />{node.attrs?.alt ? <figcaption>{String(node.attrs.alt)}</figcaption> : null}</figure> : null; }
    if (node.type === "hardBreak") return <br key={key} />;
    const tag = node.type === "heading" ? `h${node.attrs?.level}` : ({ paragraph: "p", bulletList: "ul", orderedList: "ol", listItem: "li", blockquote: "blockquote" } as Record<string, string>)[node.type];
    return tag ? createElement(tag, { key, ...(node.type === "orderedList" ? { start: Number(node.attrs?.start) || 1 } : {}) }, node.content?.map(render)) : null;
  }
  return <div className="studio-rich-content">{safe.content.map(render)}</div>;
}
