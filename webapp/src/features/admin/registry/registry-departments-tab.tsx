import { Archive, Edit3, GitMerge, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryOperationPreview, AdminRegistryPayload } from "../api";
import { formatDateTime, statusTone } from "./registry-utils";
import { RegistryOperationPreview } from "./registry-operation-preview";

type DepartmentRow = AdminRegistryPayload["departments"][number];

type Props = {
  departments: DepartmentRow[];
  onArchive: (department: DepartmentRow) => void;
  onSave: (payload: {
    departmentId?: string;
    code: string;
    name: string;
    manager_person_id: string;
    support_queue: string;
    status: string;
    notes: string;
    reason: string;
  }) => void;
  onMergePreview: (masterId: string, duplicateId: string) => Promise<AdminRegistryOperationPreview>;
  onMerge: (masterId: string, duplicateId: string, reason: string) => void;
};

export function RegistryDepartmentsTab({ departments, onArchive, onMerge, onMergePreview, onSave }: Props) {
  const [editing, setEditing] = useState<DepartmentRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-950">Подразделения</p>
        <div className="flex flex-wrap gap-2">
          <Button leadingIcon={<GitMerge className="h-4 w-4" />} onClick={() => setMergeOpen(true)} size="sm" variant="outline">Объединить</Button>
          <Button leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)} size="sm">Создать</Button>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[1020px] grid-cols-[110px_220px_160px_150px_100px_100px_120px_160px_180px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>Code</span><span>Name</span><span>Manager</span><span>Queue</span><span>Users</span><span>Devices</span><span>Status</span><span>Updated</span><span>Actions</span>
        </div>
        {departments.length ? departments.map((department) => (
          <div className="grid min-w-[1020px] grid-cols-[110px_220px_160px_150px_100px_100px_120px_160px_180px] gap-3 border-t border-border px-4 py-3 text-sm" key={department.id}>
            <span className="font-semibold text-slate-950">{department.code ?? "Нет"}</span>
            <span>{department.name}</span>
            <span>{department.manager_person_id ?? "Нет"}</span>
            <span>{department.support_queue ?? "Нет"}</span>
            <span>{department.users_count ?? 0}</span>
            <span>{department.devices_count ?? 0}</span>
            <Badge tone={statusTone(department.status)}>{department.status}</Badge>
            <span>{formatDateTime(department.updated_at)}</span>
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<Edit3 className="h-4 w-4" />} onClick={() => setEditing(department)} size="sm" variant="outline">Edit</Button>
              <Button leadingIcon={<Archive className="h-4 w-4" />} onClick={() => onArchive(department)} size="sm" variant="ghost">Archive</Button>
            </div>
          </div>
        )) : <p className="border-t border-border px-4 py-6 text-sm text-slate-500">Подразделения не найдены.</p>}
      </div>
      <DepartmentDialog department={editing} open={creating || Boolean(editing)} onClose={() => { setCreating(false); setEditing(null); }} onSave={onSave} />
      <DepartmentMergeDialog departments={departments} open={mergeOpen} onClose={() => setMergeOpen(false)} onMerge={onMerge} onPreview={onMergePreview} />
    </div>
  );
}

function DepartmentDialog({ department, onClose, onSave, open }: {
  department: DepartmentRow | null;
  open: boolean;
  onClose: () => void;
  onSave: Props["onSave"];
}) {
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [manager, setManager] = useState("");
  const [queue, setQueue] = useState("");
  const [status, setStatus] = useState("active");
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");
  useEffect(() => {
    setCode(department?.code ?? "");
    setName(department?.name ?? "");
    setManager(department?.manager_person_id ?? "");
    setQueue(department?.support_queue ?? "");
    setStatus(department?.status ?? "active");
    setNotes(department?.notes ?? "");
    setReason("");
  }, [department, open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>{department ? "Редактировать подразделение" : "Создать подразделение"}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium">Code<Input className="mt-2" value={code} onChange={(event) => setCode(event.target.value)} /></label>
            <label className="block text-sm font-medium">Name<Input className="mt-2" value={name} onChange={(event) => setName(event.target.value)} /></label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium">Manager person ID<Input className="mt-2" value={manager} onChange={(event) => setManager(event.target.value)} /></label>
            <label className="block text-sm font-medium">Support queue<Input className="mt-2" value={queue} onChange={(event) => setQueue(event.target.value)} /></label>
          </div>
          <label className="block text-sm font-medium">Status<Input className="mt-2" value={status} onChange={(event) => setStatus(event.target.value)} /></label>
          <label className="block text-sm font-medium">Notes<Input className="mt-2" value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          <label className="block text-sm font-medium">Reason<Input className="mt-2" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button disabled={!name.trim() || !reason.trim()} onClick={() => onSave({ departmentId: department?.department_id ?? department?.id, code, name, manager_person_id: manager, support_queue: queue, status, notes, reason })}>Сохранить</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function DepartmentMergeDialog({ departments, onClose, onMerge, onPreview, open }: {
  departments: DepartmentRow[];
  open: boolean;
  onClose: () => void;
  onMerge: Props["onMerge"];
  onPreview: Props["onMergePreview"];
}) {
  const [masterId, setMasterId] = useState("");
  const [duplicateId, setDuplicateId] = useState("");
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<AdminRegistryOperationPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewBusy, setPreviewBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setMasterId("");
    setDuplicateId("");
    setReason("");
    setPreview(null);
    setPreviewError(null);
  }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>Объединить подразделения</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <select className="field-base h-11 w-full px-3" value={masterId} onChange={(event) => { setMasterId(event.target.value); setPreview(null); }}>
            <option value="">Master</option>
            {departments.map((item) => <option key={item.id} value={item.department_id ?? item.id}>{item.code ? `${item.code} - ${item.name}` : item.name}</option>)}
          </select>
          <select className="field-base h-11 w-full px-3" value={duplicateId} onChange={(event) => { setDuplicateId(event.target.value); setPreview(null); }}>
            <option value="">Duplicate</option>
            {departments.map((item) => <option key={item.id} value={item.department_id ?? item.id}>{item.code ? `${item.code} - ${item.name}` : item.name}</option>)}
          </select>
          <Input placeholder="Причина" value={reason} onChange={(event) => setReason(event.target.value)} />
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
                  setPreview(await onPreview(masterId, duplicateId));
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
            <Button disabled={!masterId || !duplicateId || masterId === duplicateId || !reason.trim() || !preview} onClick={() => onMerge(masterId, duplicateId, reason)}>Объединить</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
