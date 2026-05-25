import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryImportPreview, AdminRegistryImportType } from "../api";
import { RegistryOperationPreview } from "./registry-operation-preview";

type Props = {
  busy: boolean;
  open: boolean;
  onApply: (payload: { type: AdminRegistryImportType; csv_text: string; preview_id: string; reason: string }) => void;
  onClose: () => void;
  onPreview: (payload: { type: AdminRegistryImportType; csv_text: string }) => Promise<AdminRegistryImportPreview>;
};

const importTypes: Array<{ value: AdminRegistryImportType; label: string }> = [
  { value: "people", label: "People" },
  { value: "locations", label: "Locations" },
  { value: "departments", label: "Departments" },
  { value: "device_inventory_mapping", label: "Device inventory mapping" },
];

export function RegistryImportDialog({ busy, onApply, onClose, onPreview, open }: Props) {
  const [type, setType] = useState<AdminRegistryImportType>("people");
  const [csvText, setCsvText] = useState("");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<AdminRegistryImportPreview | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setType("people");
    setCsvText("");
    setReason("");
    setPreview(null);
    setError(null);
  }, [open]);

  if (!open) return null;

  const hasBlockers = Boolean((preview?.row_errors?.length ?? 0) || (preview?.duplicate_keys?.length ?? 0));
  const canApply = Boolean(preview && !hasBlockers && reason.trim() && csvText.trim() && !busy);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-4xl">
        <CardHeader>
          <CardTitle>Registry CSV import</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[240px_1fr]">
            <select
              className="field-base h-11 w-full px-3 text-sm"
              onChange={(event) => {
                setType(event.target.value as AdminRegistryImportType);
                setPreview(null);
              }}
              value={type}
            >
              {importTypes.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <Input onChange={(event) => setReason(event.target.value)} placeholder="Reason for apply" value={reason} />
          </div>
          <textarea
            className="field-base min-h-[220px] w-full px-3 py-2 font-mono text-xs"
            onChange={(event) => {
              setCsvText(event.target.value);
              setPreview(null);
            }}
            placeholder="Paste CSV with a header row. Bindings import is intentionally not supported here."
            value={csvText}
          />
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <RegistryOperationPreview preview={preview} />
          {preview?.row_errors?.length ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">
              <div className="font-semibold">Row errors</div>
              <ul className="mt-2 max-h-32 space-y-1 overflow-auto">
                {preview.row_errors.slice(0, 10).map((item) => (
                  <li key={`${item.row}-${item.field}-${item.message}`}>row {item.row}: {item.field ? `${item.field} - ` : ""}{item.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {preview?.duplicate_keys?.length ? (
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-950">
              <div className="font-semibold">Duplicates</div>
              <ul className="mt-2 max-h-32 space-y-1 overflow-auto">
                {preview.duplicate_keys.slice(0, 10).map((item) => (
                  <li key={`${item.row}-${item.key}-${item.value}`}>row {item.row}: {item.key}={item.value} - {item.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Cancel</Button>
            <Button
              disabled={!csvText.trim() || previewBusy}
              onClick={async () => {
                setPreviewBusy(true);
                setError(null);
                try {
                  setPreview(await onPreview({ type, csv_text: csvText }));
                } catch (previewError) {
                  setError(previewError instanceof Error ? previewError.message : "Import preview failed");
                } finally {
                  setPreviewBusy(false);
                }
              }}
              variant="outline"
            >
              {previewBusy ? "Validating..." : "Preview"}
            </Button>
            <Button disabled={!canApply} onClick={() => preview && onApply({ type, csv_text: csvText, preview_id: preview.preview_id, reason })}>
              {busy ? "Applying..." : "Apply import"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
