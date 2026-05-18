import { Check, RotateCcw, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import type { CapabilityDescriptor, ToolPresentationDetail } from "../../features/capabilities/types";
import { cn } from "../../shared/ui/cn";
import {
  CompositeRecipeRenderer,
  ModuleResultRenderer,
  normalizePresentationSchema,
  type PresentationSchema,
} from "./module-result-renderer";
import { extractSchemaPaths, generateMockSampleFromSchema, type SchemaPathItem } from "./schema-path-picker";

const FALLBACK_SCHEMA = {
  version: "1.0",
  kind: "tool_result",
  blocks: [{ type: "raw_json", collapsed: true }],
  fallback: { show_raw_json: true },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function schemaForEditor(capability: CapabilityDescriptor, detail?: ToolPresentationDetail | null): unknown {
  if (detail?.override_schema) {
    return detail.override_schema;
  }
  if (detail?.effective_schema && isRecord(detail.effective_schema) && Object.keys(detail.effective_schema).length) {
    return detail.effective_schema;
  }
  if (capability.effective_presentation_schema && isRecord(capability.effective_presentation_schema)) {
    return capability.effective_presentation_schema;
  }
  if (capability.presentation_schema && isRecord(capability.presentation_schema)) {
    return capability.presentation_schema;
  }
  return FALLBACK_SCHEMA;
}

function sourceFor(capability: CapabilityDescriptor, detail?: ToolPresentationDetail | null): ToolPresentationDetail["source"] {
  if (detail?.source) {
    return detail.source;
  }
  if (capability.presentation_schema_source === "server_override") {
    return "server_override";
  }
  if (capability.presentation_schema_source === "module_default" || isRecord(capability.presentation_schema)) {
    return "module_default";
  }
  return "none";
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function parseJsonObject(value: string, label: string): { value: Record<string, unknown> | null; error: string | null } {
  try {
    const parsed = JSON.parse(value);
    if (!isRecord(parsed)) {
      return { value: null, error: `${label} must be a JSON object.` };
    }
    return { value: parsed, error: null };
  } catch (error) {
    return { value: null, error: `Invalid JSON: ${error instanceof Error ? error.message : "parse failed"}` };
  }
}

function parseAnyJson(value: string): { value: unknown; error: string | null } {
  try {
    return { value: JSON.parse(value), error: null };
  } catch (error) {
    return { value: null, error: `Invalid sample JSON: ${error instanceof Error ? error.message : "parse failed"}` };
  }
}

function sourceTone(source: ToolPresentationDetail["source"]): "neutral" | "brand" | "info" {
  if (source === "server_override") {
    return "brand";
  }
  if (source === "module_default") {
    return "info";
  }
  return "neutral";
}

function PathPicker({ onSelect, paths }: { onSelect: (path: string) => void; paths: SchemaPathItem[] }) {
  if (!paths.length) {
    return <p className="rounded-lg border border-dashed border-border bg-surface-subtle p-3 text-sm text-slate-500">No paths found in output_schema.</p>;
  }
  return (
    <div className="max-h-80 space-y-2 overflow-auto pr-1">
      {paths.map((item) => (
        <button
          aria-label={`${item.path} ${item.type}`}
          className="flex w-full items-start justify-between gap-3 rounded-lg border border-border bg-white px-3 py-2 text-left hover:border-brand-200 hover:bg-brand-50"
          key={`${item.path}:${item.type}`}
          onClick={() => onSelect(item.path)}
          type="button"
        >
          <span className="min-w-0">
            <span className="block break-all text-xs font-semibold text-slate-900">{item.path}</span>
            <span className="mt-1 block text-xs text-slate-500">{item.label}</span>
          </span>
          <span className="shrink-0 rounded-md bg-slate-100 px-2 py-1 text-[0.68rem] font-semibold uppercase text-slate-500">
            {item.type}
          </span>
        </button>
      ))}
    </div>
  );
}

export type PresentationSchemaBuilderProps = {
  capability: CapabilityDescriptor;
  detail?: ToolPresentationDetail | null;
  onSave?: (schema: unknown) => Promise<ToolPresentationDetail>;
  onReset?: () => Promise<ToolPresentationDetail>;
};

export function PresentationSchemaBuilder({ capability, detail, onSave, onReset }: PresentationSchemaBuilderProps) {
  const initialSchema = useMemo(() => schemaForEditor(capability, detail), [capability, detail]);
  const initialSource = useMemo(() => sourceFor(capability, detail), [capability, detail]);
  const generatedSample = useMemo(() => generateMockSampleFromSchema(capability.output_schema), [capability.output_schema]);
  const paths = useMemo(() => extractSchemaPaths(capability.output_schema), [capability.output_schema]);
  const [schemaText, setSchemaText] = useState(() => prettyJson(initialSchema));
  const [sampleText, setSampleText] = useState(() => prettyJson(generatedSample));
  const [source, setSource] = useState<ToolPresentationDetail["source"]>(() => sourceFor(capability, detail));
  const [validationError, setValidationError] = useState<string | null>(null);
  const [sampleError, setSampleError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const editorRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    setSchemaText(prettyJson(initialSchema));
    setSource(initialSource);
    setValidationError(null);
    setSaveState("idle");
  }, [capability.id, detail, initialSchema, initialSource]);

  useEffect(() => {
    setSampleText(prettyJson(generatedSample));
    setSampleError(null);
  }, [capability.id, generatedSample]);

  const parsedSchema = parseJsonObject(schemaText, "Presentation schema");
  const parsedSample = parseAnyJson(sampleText);
  const previewSchema = parsedSchema.value ? normalizePresentationSchema(parsedSchema.value) : null;
  const sampleResult = parsedSample.error ? {} : parsedSample.value;

  function insertPath(path: string): void {
    const editor = editorRef.current;
    if (!editor) {
      setSchemaText((current) => `${current}\n${path}`);
      return;
    }
    const start = editor.selectionStart ?? schemaText.length;
    const end = editor.selectionEnd ?? schemaText.length;
    const next = `${schemaText.slice(0, start)}${path}${schemaText.slice(end)}`;
    setSchemaText(next);
    window.setTimeout(() => {
      editor.focus();
      editor.setSelectionRange(start + path.length, start + path.length);
    }, 0);
  }

  function validateNow(): void {
    setValidationError(parsedSchema.error);
    setSampleError(parsedSample.error);
    if (!parsedSchema.error && !parsedSample.error) {
      setSaveState("idle");
    }
  }

  async function save(): Promise<void> {
    const parsed = parseJsonObject(schemaText, "Presentation schema");
    setValidationError(parsed.error);
    if (parsed.error || !parsed.value || !onSave) {
      return;
    }
    setSaveState("saving");
    const next = await onSave(parsed.value);
    setSource(next.source);
    setSchemaText(prettyJson(next.override_schema ?? next.effective_schema ?? parsed.value));
    setSaveState("saved");
  }

  async function reset(): Promise<void> {
    if (!onReset) {
      return;
    }
    const next = await onReset();
    setSource(next.source);
    setSchemaText(prettyJson(next.effective_schema ?? FALLBACK_SCHEMA));
    setSaveState("idle");
  }

  function formatJson(): void {
    if (!parsedSchema.value) {
      setValidationError(parsedSchema.error);
      return;
    }
    setSchemaText(prettyJson(parsedSchema.value));
    setValidationError(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-950">{capability.title || capability.id}</p>
          <p className="mt-1 break-all text-xs text-slate-500">{capability.id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={sourceTone(source)}>{source.replace("_", " ")}</Badge>
          <Button
            onClick={() => {
              editorRef.current?.focus();
            }}
            size="sm"
            variant="outline"
          >
            Edit override
          </Button>
          <Button onClick={validateNow} size="sm" variant="outline" leadingIcon={<Check className="h-4 w-4" />}>
            Validate
          </Button>
          <Button onClick={formatJson} size="sm" variant="outline">
            Format JSON
          </Button>
          <Button disabled={!onSave || saveState === "saving"} onClick={save} size="sm" leadingIcon={<Save className="h-4 w-4" />}>
            Save
          </Button>
          <Button disabled={!onReset} onClick={reset} size="sm" variant="ghost" leadingIcon={<RotateCcw className="h-4 w-4" />}>
            Reset override
          </Button>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(13rem,0.8fr)_minmax(18rem,1.2fr)_minmax(18rem,1fr)]">
        <section className="space-y-3 rounded-lg border border-border bg-surface-subtle p-4">
          <div>
            <h4 className="text-sm font-semibold text-slate-950">Output schema paths</h4>
            <p className="mt-1 text-xs text-slate-500">Click a path to insert it into the JSON editor.</p>
          </div>
          <PathPicker onSelect={insertPath} paths={paths} />
        </section>

        <section className="space-y-3 rounded-lg border border-border bg-white p-4">
          <label className="block text-sm font-semibold text-slate-950" htmlFor="presentation-schema-json">
            Presentation schema JSON
          </label>
          <textarea
            aria-label="Presentation schema JSON"
            className={cn(
              "min-h-96 w-full resize-y rounded-lg border border-border bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100 outline-none focus:border-brand-400",
              validationError ? "border-rose-300" : "",
            )}
            id="presentation-schema-json"
            onChange={(event) => {
              setSchemaText(event.target.value);
              setValidationError(null);
              setSaveState("idle");
            }}
            ref={editorRef}
            value={schemaText}
          />
          {validationError ? <p className="text-sm text-rose-700">{validationError}</p> : null}
          {saveState === "saved" ? <p className="text-sm text-emerald-700">Override saved.</p> : null}

          <label className="block text-sm font-semibold text-slate-950" htmlFor="presentation-sample-json">
            Sample result JSON
          </label>
          <textarea
            aria-label="Sample result JSON"
            className={cn(
              "min-h-40 w-full resize-y rounded-lg border border-border bg-white p-3 font-mono text-xs leading-5 text-slate-800 outline-none focus:border-brand-400",
              sampleError ? "border-rose-300" : "",
            )}
            id="presentation-sample-json"
            onChange={(event) => {
              setSampleText(event.target.value);
              setSampleError(null);
            }}
            value={sampleText}
          />
          {sampleError ? <p className="text-sm text-rose-700">{sampleError}</p> : null}
        </section>

        <section className="space-y-3 rounded-lg border border-border bg-surface-subtle p-4">
          <h4 className="text-sm font-semibold text-slate-950">Live preview</h4>
          {!previewSchema ? (
            <p className="rounded-lg border border-dashed border-border bg-white p-3 text-sm text-slate-500">
              Preview is limited until the schema JSON is valid.
            </p>
          ) : previewSchema.kind === "composite_recipe" ? (
            <CompositeRecipeRenderer result={sampleResult} presentationSchema={previewSchema as PresentationSchema} />
          ) : (
            <ModuleResultRenderer result={sampleResult} presentationSchema={previewSchema as PresentationSchema} />
          )}
        </section>
      </div>
    </div>
  );
}
