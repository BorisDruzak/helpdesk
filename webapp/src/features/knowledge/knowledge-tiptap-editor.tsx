import { useEffect, type FormEvent } from "react";
import Highlight from "@tiptap/extension-highlight";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Bold, Code2, Heading2, Highlighter, Italic, List, Quote } from "lucide-react";

import { Button } from "../../components/ui/button";

type KnowledgeTemplateOption = {
  sections: string[];
  title: string;
  type: string;
};

type TipTapNode = {
  attrs?: Record<string, unknown>;
  content?: TipTapNode[];
  marks?: Array<{ attrs?: Record<string, unknown>; type?: string }>;
  text?: string;
  type?: string;
};

type KnowledgeTipTapEditorProps = {
  isDisabled?: boolean;
  onChange: (value: string) => void;
  onInsertBlock: (block: string) => void;
  onInsertTemplate: (sections: string[]) => void;
  templates: KnowledgeTemplateOption[];
  value: string;
};

const visualMarks = [
  { label: "Ручная разметка", color: "#fef3c7", className: "bg-amber-100 text-amber-950" },
  { label: "AI-предложение", color: "#dbeafe", className: "bg-sky-100 text-sky-950" },
  { label: "Автосегмент", color: "#dcfce7", className: "bg-emerald-100 text-emerald-950" },
  { label: "Изменённый текст", color: "#ffe4e6", className: "bg-rose-100 text-rose-950" },
];

function escapeHtml(value: string) {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderInlineMarkdown(value: string) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function markdownToHtml(markdown: string) {
  const blocks = markdown.trim().split(/\n{2,}/).filter(Boolean);
  if (!blocks.length) {
    return "<p></p>";
  }
  return blocks
    .map((block) => {
      if (block.startsWith("```")) {
        const lines = block.split("\n");
        const language = lines[0].replace(/^```/, "").trim();
        const body = lines.slice(1).join("\n").replace(/```$/, "").trim();
        return `<pre><code class="language-${escapeHtml(language || "text")}">${escapeHtml(body)}</code></pre>`;
      }
      if (block.startsWith("# ")) {
        return `<h1>${renderInlineMarkdown(block.slice(2).trim())}</h1>`;
      }
      if (block.startsWith("## ")) {
        return `<h2>${renderInlineMarkdown(block.slice(3).trim())}</h2>`;
      }
      if (block.startsWith("### ")) {
        return `<h3>${renderInlineMarkdown(block.slice(4).trim())}</h3>`;
      }
      if (block.split("\n").every((line) => line.trim().startsWith("- "))) {
        const items = block
          .split("\n")
          .map((line) => `<li>${renderInlineMarkdown(line.replace(/^- /, "").trim())}</li>`)
          .join("");
        return `<ul>${items}</ul>`;
      }
      if (block.startsWith("> ")) {
        return `<blockquote>${block
          .split("\n")
          .map((line) => renderInlineMarkdown(line.replace(/^> /, "").trim()))
          .join("<br />")}</blockquote>`;
      }
      return `<p>${block
        .split("\n")
        .map((line) => renderInlineMarkdown(line.trim()))
        .join("<br />")}</p>`;
    })
    .join("");
}

function inlineText(nodes: TipTapNode[] | undefined): string {
  return (nodes ?? [])
    .map((node) => {
      if (node.type === "text") {
        let text = node.text ?? "";
        for (const mark of node.marks ?? []) {
          if (mark.type === "bold") {
            text = `**${text}**`;
          }
          if (mark.type === "italic") {
            text = `*${text}*`;
          }
          if (mark.type === "code") {
            text = `\`${text}\``;
          }
        }
        return text;
      }
      if (node.type === "hardBreak") {
        return "\n";
      }
      return inlineText(node.content);
    })
    .join("");
}

function blockToMarkdown(node: TipTapNode): string {
  if (node.type === "heading") {
    const level = typeof node.attrs?.level === "number" ? Math.min(Math.max(node.attrs.level, 1), 6) : 2;
    return `${"#".repeat(level)} ${inlineText(node.content)}`.trim();
  }
  if (node.type === "bulletList") {
    return (node.content ?? []).map((item) => `- ${inlineText(item.content).trim()}`).join("\n");
  }
  if (node.type === "orderedList") {
    return (node.content ?? []).map((item, index) => `${index + 1}. ${inlineText(item.content).trim()}`).join("\n");
  }
  if (node.type === "blockquote") {
    return inlineText(node.content)
      .split("\n")
      .map((line) => `> ${line}`)
      .join("\n");
  }
  if (node.type === "codeBlock") {
    return `\`\`\`text\n${inlineText(node.content)}\n\`\`\``;
  }
  if (node.type === "paragraph") {
    return inlineText(node.content).trim();
  }
  return inlineText(node.content).trim();
}

function serializeTipTapDocument(documentNode: TipTapNode) {
  return (documentNode.content ?? [])
    .map(blockToMarkdown)
    .filter((block) => block.trim())
    .join("\n\n");
}

export function KnowledgeTipTapEditor({ isDisabled = false, onChange, onInsertBlock, onInsertTemplate, templates, value }: KnowledgeTipTapEditorProps) {
  const editor = useEditor({
    content: markdownToHtml(value),
    editorProps: {
      attributes: {
        "aria-label": "Единый редактор статьи",
        class: "knowledge-tiptap-editor__content",
      },
    },
    extensions: [StarterKit, Highlight.configure({ multicolor: true })],
    onUpdate: ({ editor: activeEditor }) => {
      onChange(serializeTipTapDocument(activeEditor.getJSON() as TipTapNode));
    },
  });

  useEffect(() => {
    if (!editor) {
      return;
    }
    const current = serializeTipTapDocument(editor.getJSON() as TipTapNode).trim();
    if (current !== value.trim()) {
      editor.commands.setContent(markdownToHtml(value), { emitUpdate: false });
    }
  }, [editor, value]);

  function applyHighlight(color: string) {
    editor?.chain().focus().setHighlight({ color }).run();
  }

  function handleEditorInput(event: FormEvent<HTMLDivElement>) {
    const text = event.currentTarget.textContent ?? "";
    if (text.trim()) {
      onChange(text.trim());
    }
  }

  return (
    <div className="space-y-4" data-testid="knowledge-tiptap-editor">
      <div className="flex flex-wrap items-center gap-2">
        {(templates ?? []).map((template) => (
          <Button disabled={isDisabled} key={template.type} onClick={() => onInsertTemplate(template.sections)} size="sm" variant="outline">
            Вставить шаблон: {template.title}
          </Button>
        ))}
        <Button disabled={isDisabled || !editor} onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} size="icon" title="Заголовок H2" variant="outline">
          <Heading2 className="h-4 w-4" />
        </Button>
        <Button disabled={isDisabled || !editor} onClick={() => editor?.chain().focus().toggleBold().run()} size="icon" title="Жирный текст" variant="outline">
          <Bold className="h-4 w-4" />
        </Button>
        <Button disabled={isDisabled || !editor} onClick={() => editor?.chain().focus().toggleItalic().run()} size="icon" title="Курсив" variant="outline">
          <Italic className="h-4 w-4" />
        </Button>
        <Button disabled={isDisabled || !editor} onClick={() => editor?.chain().focus().toggleBulletList().run()} size="icon" title="Список" variant="outline">
          <List className="h-4 w-4" />
        </Button>
        <Button disabled={isDisabled || !editor} onClick={() => editor?.chain().focus().toggleBlockquote().run()} size="icon" title="Цитата" variant="outline">
          <Quote className="h-4 w-4" />
        </Button>
        <Button disabled={isDisabled || !editor} onClick={() => editor?.chain().focus().toggleCodeBlock().run()} size="icon" title="Кодовый блок" variant="outline">
          <Code2 className="h-4 w-4" />
        </Button>
        {visualMarks.map((mark) => (
          <Button
            aria-label={`Выделить как ${mark.label}`}
            disabled={isDisabled || !editor}
            key={mark.label}
            onClick={() => applyHighlight(mark.color)}
            size="icon"
            title={mark.label}
            variant="outline"
          >
            <Highlighter className="h-4 w-4" />
          </Button>
        ))}
      </div>

      <div className="grid gap-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs font-semibold text-slate-700 sm:grid-cols-4">
        {visualMarks.map((mark) => (
          <span className={`rounded-md px-2 py-1 ${mark.className}`} key={mark.label}>
            {mark.label}
          </span>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        <Button disabled={isDisabled} onClick={() => onInsertBlock("> [!NOTE]\n> Важное уточнение для читателя.")} size="sm" variant="outline">
          Callout
        </Button>
        <Button disabled={isDisabled} onClick={() => onInsertBlock("| Шаг | Действие |\n| --- | --- |\n| 1 | Описать проверку |")} size="sm" variant="outline">
          Таблица
        </Button>
        <Button disabled={isDisabled} onClick={() => onInsertBlock("```text\nКоманда или лог\n```")} size="sm" variant="outline">
          Код
        </Button>
        <Button disabled={isDisabled} onClick={() => onInsertBlock("- [ ] Проверить результат\n- [ ] Обновить статью после проверки")} size="sm" variant="outline">
          Checklist
        </Button>
      </div>

      <div className="knowledge-tiptap-editor rounded-md border border-slate-200 bg-white">
        <EditorContent data-testid="knowledge-editor-content" editor={editor} onInput={handleEditorInput} />
      </div>
    </div>
  );
}
