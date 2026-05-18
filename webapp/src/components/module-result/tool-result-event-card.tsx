import {
  CompositeRecipeRenderer,
  ModuleResultRenderer,
  type PresentationSchema,
} from "./module-result-renderer";

type ToolResultEventCardProps = {
  result: unknown;
  presentationSchema?: unknown;
};

function isCompositeRecipeSchema(schema: unknown): schema is PresentationSchema {
  return typeof schema === "object" && schema !== null && (schema as { kind?: unknown }).kind === "composite_recipe";
}

export function ToolResultEventCard({ result, presentationSchema }: ToolResultEventCardProps) {
  const schema = presentationSchema as PresentationSchema | undefined;
  return (
    <div className="mt-3 rounded-lg border border-white/10 bg-slate-100 p-3 text-slate-950">
      {isCompositeRecipeSchema(schema) ? (
        <CompositeRecipeRenderer result={result} presentationSchema={schema} />
      ) : (
        <ModuleResultRenderer result={result} presentationSchema={schema} />
      )}
    </div>
  );
}
