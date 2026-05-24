import { useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryPayload } from "../api";

type Person = AdminRegistryPayload["people"][number];

type Props = {
  people: Person[];
  initialDuplicateId?: string | null;
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: {
    master_person_id: string;
    duplicate_person_id: string;
    field_strategy: Record<string, "master" | "duplicate">;
    reason: string;
  }) => void;
};

const fields = ["full_name", "display_name", "email", "phone", "department_id", "location_id"] as const;

export function RegistryMergePeopleDialog({ initialDuplicateId, onClose, onSubmit, open, people }: Props) {
  const [masterId, setMasterId] = useState("");
  const [duplicateId, setDuplicateId] = useState(initialDuplicateId ?? "");
  const [reason, setReason] = useState("");
  const [strategy, setStrategy] = useState<Record<string, "master" | "duplicate">>({});
  if (!open) return null;
  const master = people.find((item) => item.person_id === masterId);
  const duplicate = people.find((item) => item.person_id === duplicateId);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-3xl">
        <CardHeader><CardTitle>Слияние пользователей</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <select className="field-base h-11 w-full px-3" value={masterId} onChange={(event) => setMasterId(event.target.value)}>
              <option value="">Master user</option>
              {people.map((person) => <option key={person.person_id} value={person.person_id}>{person.display_name}</option>)}
            </select>
            <select className="field-base h-11 w-full px-3" value={duplicateId} onChange={(event) => setDuplicateId(event.target.value)}>
              <option value="">Duplicate user</option>
              {people.map((person) => <option key={person.person_id} value={person.person_id}>{person.display_name}</option>)}
            </select>
          </div>
          {master && duplicate ? (
            <div className="overflow-x-auto rounded-lg border border-border">
              <div className="grid min-w-[720px] grid-cols-[160px_220px_220px_120px] bg-slate-50 px-3 py-2 text-xs font-semibold uppercase text-slate-500">
                <span>Field</span><span>Master</span><span>Duplicate</span><span>Winner</span>
              </div>
              {fields.map((field) => (
                <div className="grid min-w-[720px] grid-cols-[160px_220px_220px_120px] border-t border-border px-3 py-2 text-sm" key={field}>
                  <span>{field}</span>
                  <span>{String(master[field] ?? "Нет")}</span>
                  <span>{String(duplicate[field] ?? "Нет")}</span>
                  <select className="field-base h-9 px-2 text-sm" value={strategy[field] ?? "master"} onChange={(event) => setStrategy({ ...strategy, [field]: event.target.value as "master" | "duplicate" })}>
                    <option value="master">master</option>
                    <option value="duplicate">duplicate</option>
                  </select>
                </div>
              ))}
            </div>
          ) : null}
          <Input placeholder="Причина слияния" value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={!masterId || !duplicateId || masterId === duplicateId || !reason.trim()}
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
