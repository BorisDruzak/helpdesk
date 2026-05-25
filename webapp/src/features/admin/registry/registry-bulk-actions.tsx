import { ClipboardCopy, Download, Eye, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "../../../components/ui/button";
import type { AdminRegistryBulkResponse } from "../api";

export type RegistryBulkAction = {
  key: string;
  label: string;
};

type Props = {
  actions: RegistryBulkAction[];
  busy: boolean;
  result: AdminRegistryBulkResponse | null;
  selectedCount: number;
  onAction: (key: string) => void;
  onClearResult: () => void;
  onClearSelection: () => void;
};

function csvSafe(value: unknown): string {
  const text = String(value ?? "");
  const formulaSafe = /^[=+\-@]/.test(text) ? `'${text}` : text;
  const escaped = formulaSafe.replaceAll('"', '""');
  return `"${escaped}"`;
}

function resultCsv(result: AdminRegistryBulkResponse): string {
  const rows = ["id,status,error_code,error,affected_sessions"];
  for (const item of result.items) {
    rows.push([
      item.id,
      item.status,
      item.error_code ?? "",
      item.error ?? "",
      item.affected_sessions ?? "",
    ].map(csvSafe).join(","));
  }
  return `${rows.join("\n")}\n`;
}

function downloadResult(result: AdminRegistryBulkResponse) {
  const blob = new Blob([resultCsv(result)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `registry-bulk-${result.bulk_operation_id}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function RegistryBulkActions({ actions, busy, onAction, onClearResult, onClearSelection, result, selectedCount }: Props) {
  const [showFailed, setShowFailed] = useState(false);
  const failedItems = useMemo(() => result?.items.filter((item) => item.status === "error") ?? [], [result]);
  if (!selectedCount && !result) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border bg-slate-50 px-3 py-3">
      {selectedCount ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">Selected: {selectedCount}</span>
          {actions.map((action) => (
            <Button disabled={busy} key={action.key} onClick={() => onAction(action.key)} size="sm" variant="outline">
              {action.label}
            </Button>
          ))}
          <Button leadingIcon={<X className="h-4 w-4" />} onClick={onClearSelection} size="sm" variant="ghost">Clear</Button>
        </div>
      ) : null}
      {result ? (
        <div className="mt-3 rounded-md border border-slate-200 bg-white p-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-semibold text-slate-900">Bulk result</span>
            <span className="text-sm text-slate-600">selected: {result.summary.selected}</span>
            <span className="text-sm text-emerald-700">success: {result.summary.success}</span>
            <span className="text-sm text-rose-700">failed: {result.summary.failed}</span>
            <Button disabled={!failedItems.length} leadingIcon={<Eye className="h-4 w-4" />} onClick={() => setShowFailed((value) => !value)} size="sm" variant="outline">
              {showFailed ? "Hide failed" : "Show failed"}
            </Button>
            <Button
              disabled={!failedItems.length}
              leadingIcon={<ClipboardCopy className="h-4 w-4" />}
              onClick={() => void navigator.clipboard?.writeText(failedItems.map((item) => `${item.id}: ${item.error_code ?? item.error ?? "error"}`).join("\n"))}
              size="sm"
              variant="outline"
            >
              Copy errors
            </Button>
            <Button leadingIcon={<Download className="h-4 w-4" />} onClick={() => downloadResult(result)} size="sm" variant="outline">Export result</Button>
            <Button leadingIcon={<X className="h-4 w-4" />} onClick={onClearResult} size="sm" variant="ghost">Dismiss</Button>
          </div>
          {showFailed && failedItems.length ? (
            <ul className="mt-3 max-h-40 space-y-1 overflow-auto text-sm text-rose-800">
              {failedItems.map((item) => (
                <li className="rounded-md bg-rose-50 px-2 py-1" key={item.id}>
                  <span className="font-mono">{item.id}</span>
                  <span className="mx-2">-</span>
                  <span>{item.error_code ?? item.error ?? "error"}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
