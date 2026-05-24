import { Archive, Edit3, GitMerge, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryOperationPreview, AdminRegistryPayload } from "../api";
import { formatDateTime, statusTone } from "./registry-utils";
import { Badge } from "../../../components/ui/badge";
import { RegistryOperationPreview } from "./registry-operation-preview";

type LocationRow = AdminRegistryPayload["locations"][number];

type Props = {
  locations: LocationRow[];
  onArchive: (location: LocationRow) => void;
  onSave: (payload: {
    locationId?: string;
    building: string;
    floor: string;
    room: string;
    display_name: string;
    status: string;
    notes: string;
    reason: string;
  }) => void;
  onMergePreview: (masterId: string, duplicateId: string) => Promise<AdminRegistryOperationPreview>;
  onMerge: (masterId: string, duplicateId: string, reason: string) => void;
};

export function RegistryLocationsTab({ locations, onArchive, onMerge, onMergePreview, onSave }: Props) {
  const [editing, setEditing] = useState<LocationRow | null>(null);
  const [creating, setCreating] = useState(false);
  const [mergeOpen, setMergeOpen] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-slate-950">Локации</p>
        <div className="flex flex-wrap gap-2">
          <Button leadingIcon={<GitMerge className="h-4 w-4" />} onClick={() => setMergeOpen(true)} size="sm" variant="outline">Объединить</Button>
          <Button leadingIcon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)} size="sm">Создать</Button>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <div className="grid min-w-[980px] grid-cols-[220px_140px_90px_120px_100px_100px_120px_160px_180px] gap-3 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
          <span>Название</span><span>Здание</span><span>Этаж</span><span>Кабинет</span><span>Users</span><span>Devices</span><span>Status</span><span>Updated</span><span>Actions</span>
        </div>
        {locations.length ? locations.map((location) => (
          <div className="grid min-w-[980px] grid-cols-[220px_140px_90px_120px_100px_100px_120px_160px_180px] gap-3 border-t border-border px-4 py-3 text-sm" key={location.id}>
            <span className="font-semibold text-slate-950">{location.display_name}</span>
            <span>{location.building ?? "Не указано"}</span>
            <span>{location.floor ?? "Нет"}</span>
            <span>{location.room ?? "Нет"}</span>
            <span>{location.users_count ?? 0}</span>
            <span>{location.devices_count ?? 0}</span>
            <Badge tone={statusTone(location.status)}>{location.status}</Badge>
            <span>{formatDateTime(location.updated_at)}</span>
            <div className="flex flex-wrap gap-2">
              <Button leadingIcon={<Edit3 className="h-4 w-4" />} onClick={() => setEditing(location)} size="sm" variant="outline">Edit</Button>
              <Button leadingIcon={<Archive className="h-4 w-4" />} onClick={() => onArchive(location)} size="sm" variant="ghost">Archive</Button>
            </div>
          </div>
        )) : (
          <p className="border-t border-border px-4 py-6 text-sm text-slate-500">Локации не найдены.</p>
        )}
      </div>
      <LocationDialog location={editing} open={creating || Boolean(editing)} onClose={() => { setCreating(false); setEditing(null); }} onSave={onSave} />
      <LocationMergeDialog locations={locations} open={mergeOpen} onClose={() => setMergeOpen(false)} onMerge={onMerge} onPreview={onMergePreview} />
    </div>
  );
}

function LocationDialog({ location, onClose, onSave, open }: {
  location: LocationRow | null;
  open: boolean;
  onClose: () => void;
  onSave: Props["onSave"];
}) {
  const [building, setBuilding] = useState("");
  const [floor, setFloor] = useState("");
  const [room, setRoom] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [status, setStatus] = useState("active");
  const [notes, setNotes] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    setBuilding(location?.building ?? "");
    setFloor(location?.floor ?? "");
    setRoom(location?.room ?? "");
    setDisplayName(location?.display_name ?? "");
    setStatus(location?.status ?? "active");
    setNotes(location?.notes ?? "");
    setReason("");
  }, [location, open]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>{location ? "Редактировать локацию" : "Создать локацию"}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <label className="block text-sm font-medium">Здание<Input className="mt-2" value={building} onChange={(event) => setBuilding(event.target.value)} /></label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium">Этаж<Input className="mt-2" value={floor} onChange={(event) => setFloor(event.target.value)} /></label>
            <label className="block text-sm font-medium">Кабинет<Input className="mt-2" value={room} onChange={(event) => setRoom(event.target.value)} /></label>
          </div>
          <label className="block text-sm font-medium">Название<Input className="mt-2" value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label>
          <label className="block text-sm font-medium">Статус<Input className="mt-2" value={status} onChange={(event) => setStatus(event.target.value)} /></label>
          <label className="block text-sm font-medium">Заметки<Input className="mt-2" value={notes} onChange={(event) => setNotes(event.target.value)} /></label>
          <label className="block text-sm font-medium">Причина<Input className="mt-2" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button disabled={!reason.trim()} onClick={() => onSave({ locationId: location?.location_id ?? location?.id, building, floor, room, display_name: displayName, status, notes, reason })}>Сохранить</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function LocationMergeDialog({ locations, onClose, onMerge, onPreview, open }: {
  locations: LocationRow[];
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
        <CardHeader><CardTitle>Объединить локации</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <select className="field-base h-11 w-full px-3" value={masterId} onChange={(event) => { setMasterId(event.target.value); setPreview(null); }}>
            <option value="">Master</option>
            {locations.map((item) => <option key={item.id} value={item.location_id ?? item.id}>{item.display_name}</option>)}
          </select>
          <select className="field-base h-11 w-full px-3" value={duplicateId} onChange={(event) => { setDuplicateId(event.target.value); setPreview(null); }}>
            <option value="">Duplicate</option>
            {locations.map((item) => <option key={item.id} value={item.location_id ?? item.id}>{item.display_name}</option>)}
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
