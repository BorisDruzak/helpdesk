import { useEffect, useRef, useState } from "react";
import type { AdminRegistryPayload } from "../admin/api";
import { PersonProfileForm } from "./profile-panel";

export function CreatePersonDialog({ registry, onClose, onSaved }: { registry: AdminRegistryPayload; onClose: () => void; onSaved: (personId: string) => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    dialog?.showModal();
    dialog?.querySelector<HTMLInputElement>("input")?.focus();
    return () => { dialog?.close(); if (opener?.isConnected) opener.focus(); };
  }, []);
  return <dialog ref={dialogRef} aria-labelledby="create-user-title" className="m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-2xl overflow-y-auto rounded-2xl border-0 bg-white p-6 shadow-xl backdrop:bg-slate-950/35" onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    <h2 id="create-user-title" className="mb-5 text-xl font-semibold">Новый профиль пользователя</h2>
    <PersonProfileForm registry={registry} onClose={onClose} onSaved={onSaved} onBusyChange={setBusy} />
  </dialog>;
}
