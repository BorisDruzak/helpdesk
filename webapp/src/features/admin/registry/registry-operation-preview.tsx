import type { AdminRegistryOperationPreview } from "../api";

type Props = {
  preview: AdminRegistryOperationPreview | null;
};

export function RegistryOperationPreview({ preview }: Props) {
  if (!preview) {
    return null;
  }
  const counts = Object.entries(preview.counts ?? {}).filter(([, value]) => typeof value === "number");
  const warnings = preview.warnings ?? [];
  const changes = preview.changes ?? [];
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-950">
      <div className="font-semibold">Предпросмотр изменений</div>
      {counts.length ? (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {counts.map(([key, value]) => (
            <div className="rounded-md bg-white/70 px-2 py-1" key={key}>
              <span className="text-xs uppercase text-amber-700">{key}</span>
              <span className="ml-2 font-semibold">{value}</span>
            </div>
          ))}
        </div>
      ) : null}
      {changes.length ? (
        <ul className="mt-3 max-h-40 space-y-1 overflow-auto">
          {changes.slice(0, 12).map((change, index) => (
            <li className="rounded-md bg-white/70 px-2 py-1" key={`${change.kind}-${change.action}-${change.object_id ?? index}`}>
              <span className="font-medium">{change.kind}</span>
              <span className="mx-1 text-amber-700">·</span>
              <span>{change.action}</span>
              {change.object_id ? <span className="ml-1 text-amber-700">{change.object_id}</span> : null}
            </li>
          ))}
          {changes.length > 12 ? <li className="px-2 text-xs text-amber-700">Еще изменений: {changes.length - 12}</li> : null}
        </ul>
      ) : null}
      {warnings.length ? <p className="mt-2 text-xs text-amber-800">Warnings: {warnings.join(", ")}</p> : null}
    </div>
  );
}
