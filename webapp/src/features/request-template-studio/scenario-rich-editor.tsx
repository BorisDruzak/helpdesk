import { useEffect, useMemo, useRef, useState } from "react";
import { EditorContent, Node, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import type { ScenarioAttachment, ScenarioRichDocument } from "./scenario-contract";
import { canonicalRichDocument, safeRichLink, scopedRichImage } from "./scenario-rich-content";
export function ScenarioRichEditor({ value, disabled, attachments = [], label, placeholder = "", onChange }: { value: ScenarioRichDocument; disabled: boolean; attachments?: ScenarioAttachment[]; label: string; placeholder?: string; onChange: (value: ScenarioRichDocument) => void }) {
  const latest = useRef({ onChange, attachments }); latest.current = { onChange, attachments };
  const [link, setLink] = useState(""), [image, setImage] = useState(""), [description, setDescription] = useState("");
  const imageExtension = useMemo(() => Node.create({
    name: "image", group: "block", atom: true,
    addAttributes: () => ({ asset_id: { default: "" }, alt: { default: "" } }),
    parseHTML: () => [],
    renderHTML({ node }) { const asset = scopedRichImage(latest.current.attachments, node.attrs.asset_id); return ["figure", { "data-scenario-image": node.attrs.asset_id }, ...(asset ? [["img", { src: asset.url, alt: node.attrs.alt || asset.name }]] : [["span", {}, "Изображение недоступно"]])]; },
  }), []);
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: { levels: [1, 2, 3] }, codeBlock: false, horizontalRule: false, underline: false, link: { openOnClick: false, autolink: false, linkOnPaste: false } }), imageExtension],
    content: value, editable: !disabled, immediatelyRender: false,
    editorProps: { attributes: state => ({ "aria-label": label, role: "textbox", "aria-multiline": "true", "aria-placeholder": placeholder, "data-placeholder": placeholder, "data-empty": String(state.doc.childCount === 1 && state.doc.firstChild?.type.name === "paragraph" && state.doc.firstChild.content.size === 0), class: "studio-rich-content studio-rich-editable nodrag nopan nowheel" }) },
    onUpdate: ({ editor }) => latest.current.onChange(canonicalRichDocument(editor.getJSON() as ScenarioRichDocument)),
  });
  useEffect(() => { editor?.setEditable(!disabled, false); }, [editor, disabled]);
  useEffect(() => { if (editor && JSON.stringify(canonicalRichDocument(editor.getJSON() as ScenarioRichDocument)) !== JSON.stringify(value)) editor.commands.setContent(value, { emitUpdate: false }); }, [editor, value]);
  if (!editor) return <p role="status">Загрузка визуального редактора…</p>;
  return <section className="space-y-2" aria-label="Визуальный редактор текста"><div className="studio-rich-toolbar" role="toolbar" aria-label="Оформление текста">
    <Button size="sm" variant="ghost" disabled={disabled} aria-label="Полужирный" onClick={() => editor.chain().focus().toggleBold().run()}><strong>Ж</strong></Button>
    <Button size="sm" variant="ghost" disabled={disabled} aria-label="Курсив" onClick={() => editor.chain().focus().toggleItalic().run()}><em>К</em></Button>
    <Button size="sm" variant="ghost" disabled={disabled} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>Заголовок</Button>
    <Button size="sm" variant="ghost" disabled={disabled} onClick={() => editor.chain().focus().toggleBulletList().run()}>Список</Button>
    <Button size="sm" variant="ghost" disabled={disabled} onClick={() => editor.chain().focus().toggleOrderedList().run()}>Шаги</Button>
    <Button size="sm" variant="ghost" disabled={disabled} onClick={() => editor.chain().focus().toggleBlockquote().run()}>Блок помощи</Button>
    <Button size="sm" variant="ghost" disabled={disabled} onClick={() => editor.chain().focus().unsetAllMarks().clearNodes().run()}>Без оформления</Button>
  </div><EditorContent editor={editor} /><details><summary>Ссылка</summary><div className="flex flex-wrap gap-2"><Input aria-label="Адрес ссылки" value={link} disabled={disabled} onChange={event => setLink(event.target.value)} placeholder="https://…" /><Button disabled={disabled || !safeRichLink(link)} variant="outline" onClick={() => { editor.chain().focus().extendMarkRange("link").setLink({ href: link }).run(); setLink(""); }}>Добавить ссылку</Button></div></details>
  {!!attachments.some(item => scopedRichImage(attachments, item.asset_id)) && <details><summary>Изображение в тексте</summary><div className="space-y-2"><Select aria-label="Изображение для вставки" value={image} disabled={disabled} onChange={event => setImage(event.target.value)}><option value="">Выберите загруженный скриншот</option>{attachments.filter(item => scopedRichImage(attachments, item.asset_id)).map(item => <option key={item.asset_id} value={item.asset_id}>{item.name}</option>)}</Select><Input aria-label="Описание изображения" maxLength={500} value={description} disabled={disabled} onChange={event => setDescription(event.target.value)} /><Button variant="outline" disabled={disabled || !image} onClick={() => { editor.chain().focus().insertContent({ type: "image", attrs: { asset_id: image, alt: description } }).run(); setImage(""); setDescription(""); }}>Вставить изображение</Button></div></details>}
  <p className="text-xs text-slate-500">Добавьте скриншот через вложения ниже, затем вставьте его в текст. Вставка и перенос файлов также доступны.</p></section>;
}
