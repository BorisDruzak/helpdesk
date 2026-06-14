import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryOperationPreview, AdminRegistryPayload } from "../api";
import { RegistryOperationPreview } from "./registry-operation-preview";

type Person = AdminRegistryPayload["people"][number];

type Props = {
  people: Person[];
  initialDuplicateId?: string | null;
  open: boolean;
  onClose: () => void;
  onPreview: (payload: {
    master_person_id: string;
    duplicate_person_id: string;
    field_strategy: Record<string, "master" | "duplicate">;
  }) => Promise<AdminRegistryOperationPreview>;
  onSubmit: (payload: {
    master_person_id: string;
    duplicate_person_id: string;
    field_strategy: Record<string, "master" | "duplicate">;
    reason: string;
  }) => void;
};

const fields = ["full_name", "display_name", "email", "phone", "department_id", "location_id"] as const;

const fieldLabels: Record<(typeof fields)[number], string> = {
  full_name: "ФИО",
  display_name: "Отображаемое имя",
  email: "Почта",
  phone: "Телефон",
  department_id: "Подразделение",
  location_id: "Локация",
};

export function RegistryMergePeopleDialog({ initialDuplicateId, onClose, onPreview, onSubmit, open, people }: Props) {
  const [masterId, setMasterId] = useState("");
  const [duplicateId, setDuplicateId] = useState(initialDuplicateId ?? "");
  const [reason, setReason] = useState("");
  const [strategy, setStrategy] = useState<Record<string, "master" | "duplicate">>({});
  const [preview, setPreview] = useState<AdminRegistryOperationPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setMasterId("");
    setDuplicateId(initialDuplicateId ?? "");
    setReason("");
    setStrategy({});
    setPreview(null);
    setPreviewError(null);
  }, [initialDuplicateId, open]);
  if (!open) return null;
  const master = people.find((item) => item.person_id === masterId);
  const duplicate = people.find((item) => item.person_id === duplicateId);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-3xl">
        <CardHeader><CardTitle>Слияние пользователей</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <select className="field-base h-11 w-full px-3" value={masterId} onChange={(event) => { setMasterId(event.target.value); setPreview(null); }}>
              <option value="">Основная карточка</option>
              {people.map((person) => <option key={person.person_id} value={person.person_id}>{person.display_name}</option>)}
            </select>
            <select className="field-base h-11 w-full px-3" value={duplicateId} onChange={(event) => { setDuplicateId(event.target.value); setPreview(null); }}>
              <option value="">Дубликат</option>
              {people.map((person) => <option key={person.person_id} value={person.person_id}>{person.display_name}</option>)}
            </select>
          </div>
          {master && duplicate ? (
            <div className="overflow-x-auto rounded-lg border border-border">
              <div className="grid min-w-[720px] grid-cols-[160px_220px_220px_120px] bg-slate-50 px-3 py-2 text-xs font-semibold uppercase text-slate-500">
                <span>Поле</span><span>Основная карточка</span><span>Дубликат</span><span>Оставить</span>
              </div>
              {fields.map((field) => (
                <div className="grid min-w-[720px] grid-cols-[160px_220px_220px_120px] border-t border-border px-3 py-2 text-sm" key={field}>
                  <span title={field}>{fieldLabels[field]}</span>
                  <span>{String(master[field] ?? "Нет")}</span>
                  <span>{String(duplicate[field] ?? "Нет")}</span>
                  <select className="field-base h-9 px-2 text-sm" value={strategy[field] ?? "master"} onChange={(event) => { setStrategy({ ...strategy, [field]: event.target.value as "master" | "duplicate" }); setPreview(null); }}>
                    <option value="master">основную</option>
                    <option value="duplicate">дубликат</option>
                  </select>
                </div>
              ))}
            </div>
          ) : null}
          <Input placeholder="Причина слияния" value={reason} onChange={(event) => setReason(event.target.value)} />
          {previewError ? <p className="text-sm text-rose-600">{previewError}</p> : null}
          <RegistryOperationPreview preview={preview} />
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={!masterId || !duplicateId || masterId === duplicateId || previewBusy}
              onClick={async () => {
                setPreviewBusy(true);
                setPreviewError(null);
                try {
                  setPreview(await onPreview({ master_person_id: masterId, duplicate_person_id: duplicateId, field_strategy: strategy }));
                } catch (error) {
                  setPreviewError(error instanceof Error ? error.message : "Не удалось построить предпросмотр");
                } finally {
                  setPreviewBusy(false);
                }
              }}
              variant="outline"
            >
              {previewBusy ? "Строим..." : "Предпросмотр"}
            </Button>
            <Button
              disabled={!masterId || !duplicateId || masterId === duplicateId || !reason.trim() || !preview}
              onClick={() => onSubmit({ master_person_id: masterId, duplicate_person_id: duplicateId, field_strategy: strategy, reason })}
            >
              Слить
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
