import { ClipboardCopy, Download, Eye } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryImportPreview, AdminRegistryImportType } from "../api";
import { RegistryOperationPreview } from "./registry-operation-preview";

type Props = {
  busy: boolean;
  open: boolean;
  onApply: (payload: { type: AdminRegistryImportType; csv_text: string; preview_id: string; reason: string }) => Promise<AdminRegistryImportPreview>;
  onClose: () => void;
  onPreview: (payload: { type: AdminRegistryImportType; csv_text: string }) => Promise<AdminRegistryImportPreview>;
};

const importTypes: Array<{ value: AdminRegistryImportType; label: string }> = [
  { value: "people", label: "Пользователи" },
  { value: "locations", label: "Локации" },
  { value: "departments", label: "Подразделения" },
  { value: "audience_groups", label: "Аудитории" },
  { value: "audience_group_members", label: "Участники аудиторий" },
  { value: "device_inventory_mapping", label: "Инвентарная привязка устройств" },
];

function csvSafe(value: unknown): string {
  const text = String(value ?? "");
  const formulaSafe = /^[=+\-@]/.test(text) ? `'${text}` : text;
  return `"${formulaSafe.replaceAll('"', '""')}"`;
}

function resultCsv(result: AdminRegistryImportPreview, failedOnly = false): string {
  const items = (result.items ?? []).filter((item) => !failedOnly || item.status === "error");
  const rows = ["row,entity_type,id,status,error_code,message,before,after"];
  for (const item of items) {
    rows.push([
      item.row ?? "",
      item.entity_type ?? "",
      item.id ?? "",
      item.status,
      item.error_code ?? "",
      item.message ?? "",
      typeof item.before === "undefined" ? "" : JSON.stringify(item.before),
      typeof item.after === "undefined" ? "" : JSON.stringify(item.after),
    ].map(csvSafe).join(","));
  }
  return `${rows.join("\n")}\n`;
}

function downloadResult(result: AdminRegistryImportPreview, failedOnly = false) {
  const blob = new Blob([resultCsv(result, failedOnly)], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `registry-import-${result.operation_id ?? result.preview_id}${failedOnly ? "-failed" : ""}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

export function RegistryImportDialog({ busy, onApply, onClose, onPreview, open }: Props) {
  const [type, setType] = useState<AdminRegistryImportType>("people");
  const [csvText, setCsvText] = useState("");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<AdminRegistryImportPreview | null>(null);
  const [applyResult, setApplyResult] = useState<AdminRegistryImportPreview | null>(null);
  const [showFailedOnly, setShowFailedOnly] = useState(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const failedItems = useMemo(() => applyResult?.items?.filter((item) => item.status === "error") ?? [], [applyResult]);

  useEffect(() => {
    if (!open) return;
    setType("people");
    setCsvText("");
    setReason("");
    setPreview(null);
    setApplyResult(null);
    setShowFailedOnly(false);
    setError(null);
  }, [open]);

  if (!open) return null;

  const hasBlockers = Boolean((preview?.row_errors?.length ?? 0) || (preview?.duplicate_keys?.length ?? 0));
  const canApply = Boolean(preview && !hasBlockers && reason.trim() && csvText.trim() && !busy);

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-4xl">
        <CardHeader>
          <CardTitle>Импорт реестра из CSV</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-[240px_1fr]">
            <select
              className="field-base h-11 w-full px-3 text-sm"
              onChange={(event) => {
                setType(event.target.value as AdminRegistryImportType);
                setPreview(null);
                setApplyResult(null);
              }}
              value={type}
            >
              {importTypes.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <Input onChange={(event) => setReason(event.target.value)} placeholder="Причина применения импорта" value={reason} />
          </div>
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-6 text-slate-600">
            Вставьте CSV с заголовком, затем сначала постройте предпросмотр. Прямой импорт привязок устройств и аккаунт-сессий намеренно запрещен; такие изменения выполняются через отдельные безопасные операции.
          </p>
          <textarea
            className="field-base min-h-[220px] w-full px-3 py-2 font-mono text-xs"
            onChange={(event) => {
              setCsvText(event.target.value);
              setPreview(null);
              setApplyResult(null);
            }}
            placeholder="Вставьте CSV с первой строкой-заголовком"
            value={csvText}
          />
          {error ? <p className="text-sm text-rose-600">{error}</p> : null}
          <RegistryOperationPreview preview={preview} />
          {preview?.row_errors?.length ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-950">
              <div className="font-semibold">Ошибки строк</div>
              <ul className="mt-2 max-h-32 space-y-1 overflow-auto">
                {preview.row_errors.slice(0, 10).map((item) => (
                  <li key={`${item.row}-${item.field}-${item.message}`}>строка {item.row}: {item.field ? `${item.field} - ` : ""}{item.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {preview?.duplicate_keys?.length ? (
            <div className="rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-950">
              <div className="font-semibold">Дубли</div>
              <ul className="mt-2 max-h-32 space-y-1 overflow-auto">
                {preview.duplicate_keys.slice(0, 10).map((item) => (
                  <li key={`${item.row}-${item.key}-${item.value}`}>строка {item.row}: {item.key}={item.value} - {item.message}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {applyResult?.operation_id ? (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-950">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-semibold">Результат импорта</span>
                <span>операция: {applyResult.operation_id}</span>
                <span>статус: {applyResult.status}</span>
                <span>успешно: {applyResult.summary?.success ?? 0}</span>
                <span>ошибки: {applyResult.summary?.failed ?? 0}</span>
                <Button disabled={!failedItems.length} leadingIcon={<Eye className="h-4 w-4" />} onClick={() => setShowFailedOnly((value) => !value)} size="sm" variant="outline">
                  {showFailedOnly ? "Показать все" : "Только ошибки"}
                </Button>
                <Button
                  disabled={!failedItems.length}
                  leadingIcon={<ClipboardCopy className="h-4 w-4" />}
                  onClick={() => void navigator.clipboard?.writeText(failedItems.map((item) => `строка ${item.row ?? item.id}: ${item.error_code ?? item.message ?? "error"}`).join("\n"))}
                  size="sm"
                  variant="outline"
                >
                  Скопировать ошибки
                </Button>
                <Button leadingIcon={<Download className="h-4 w-4" />} onClick={() => downloadResult(applyResult)} size="sm" variant="outline">Скачать отчет</Button>
                <Button disabled={!failedItems.length} leadingIcon={<Download className="h-4 w-4" />} onClick={() => downloadResult(applyResult, true)} size="sm" variant="outline">CSV с ошибками</Button>
              </div>
              {applyResult.items?.length ? (
                <ul className="mt-3 max-h-40 space-y-1 overflow-auto">
                  {applyResult.items.filter((item) => !showFailedOnly || item.status === "error").slice(0, 25).map((item, index) => (
                    <li className="rounded-md bg-white/70 px-2 py-1" key={`${item.row ?? item.id ?? index}-${item.status}`}>
                      <span className="font-mono">{item.row ? `строка ${item.row}` : item.id}</span>
                      <span className="mx-2">-</span>
                      <span>{item.status}</span>
                      {item.error_code || item.message ? <span className="ml-2 text-rose-700">{item.error_code ?? item.message}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={!csvText.trim() || previewBusy}
              onClick={async () => {
                setPreviewBusy(true);
                setError(null);
                try {
                  setPreview(await onPreview({ type, csv_text: csvText }));
                  setApplyResult(null);
                } catch (previewError) {
                  setError(previewError instanceof Error ? previewError.message : "Не удалось построить предпросмотр импорта");
                } finally {
                  setPreviewBusy(false);
                }
              }}
              variant="outline"
            >
              {previewBusy ? "Проверяем..." : "Предпросмотр"}
            </Button>
            <Button
              disabled={!canApply}
              onClick={async () => {
                if (!preview) return;
                setError(null);
                try {
                  setApplyResult(await onApply({ type, csv_text: csvText, preview_id: preview.preview_id, reason }));
                } catch (applyError) {
                  setError(applyError instanceof Error ? applyError.message : "Не удалось применить импорт");
                }
              }}
            >
              {busy ? "Применяем..." : "Применить импорт"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
