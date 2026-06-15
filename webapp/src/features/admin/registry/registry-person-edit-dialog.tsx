import { useEffect, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryPayload } from "../api";
import { registryStatusLabel } from "./registry-utils";

export type PersonEditDialogState = {
  person?: AdminRegistryPayload["people"][number];
} | null;

type Props = {
  state: PersonEditDialogState;
  onClose: () => void;
  onSubmit: (payload: {
    personId?: string;
    display_name: string;
    full_name: string;
    email: string;
    phone: string;
    position: string;
    workplace_label: string;
    internal_extension: string;
    manager_person_id: string;
    status: string;
  }) => void;
  busy?: boolean;
};

export function RegistryPersonEditDialog({ busy, onClose, onSubmit, state }: Props) {
  const [displayName, setDisplayName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [position, setPosition] = useState("");
  const [workplaceLabel, setWorkplaceLabel] = useState("");
  const [internalExtension, setInternalExtension] = useState("");
  const [managerPersonId, setManagerPersonId] = useState("");
  const [status, setStatus] = useState("active");

  useEffect(() => {
    setDisplayName(state?.person?.display_name ?? "");
    setFullName(state?.person?.full_name ?? "");
    setEmail(state?.person?.email ?? "");
    setPhone(state?.person?.phone ?? "");
    setPosition(state?.person?.position ?? "");
    setWorkplaceLabel(state?.person?.workplace_label ?? "");
    setInternalExtension(state?.person?.internal_extension ?? "");
    setManagerPersonId(state?.person?.manager_person_id ?? "");
    setStatus(state?.person?.status ?? "active");
  }, [state]);

  if (!state) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>{state.person ? "Редактировать пользователя" : "Создать пользователя"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">Отображаемое имя<Input className="mt-2" onChange={(event) => setDisplayName(event.target.value)} value={displayName} /></label>
          <label className="block text-sm font-medium text-slate-700">ФИО<Input className="mt-2" onChange={(event) => setFullName(event.target.value)} value={fullName} /></label>
          <label className="block text-sm font-medium text-slate-700">Почта<Input className="mt-2" onChange={(event) => setEmail(event.target.value)} value={email} /></label>
          <label className="block text-sm font-medium text-slate-700">Телефон<Input className="mt-2" onChange={(event) => setPhone(event.target.value)} value={phone} /></label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">Должность<Input className="mt-2" onChange={(event) => setPosition(event.target.value)} value={position} /></label>
            <label className="block text-sm font-medium text-slate-700">Рабочее место<Input className="mt-2" onChange={(event) => setWorkplaceLabel(event.target.value)} value={workplaceLabel} /></label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">Внутренний номер<Input className="mt-2" onChange={(event) => setInternalExtension(event.target.value)} value={internalExtension} /></label>
            <label className="block text-sm font-medium text-slate-700">ID руководителя<Input className="mt-2" onChange={(event) => setManagerPersonId(event.target.value)} value={managerPersonId} /></label>
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Статус
            <select className="field-base mt-2 h-11 w-full px-3 text-sm" onChange={(event) => setStatus(event.target.value)} value={status}>
              <option value="active">{registryStatusLabel("active")}</option>
              <option value="self_reported">{registryStatusLabel("self_reported")}</option>
              <option value="inactive">{registryStatusLabel("inactive")}</option>
              <option value="disabled">{registryStatusLabel("disabled")}</option>
            </select>
          </label>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={busy || !displayName.trim()}
              onClick={() => onSubmit({
                personId: state.person?.person_id,
                display_name: displayName.trim(),
                full_name: fullName.trim(),
                email: email.trim(),
                phone: phone.trim(),
                position: position.trim(),
                workplace_label: workplaceLabel.trim(),
                internal_extension: internalExtension.trim(),
                manager_person_id: managerPersonId.trim(),
                status,
              })}
            >
              Сохранить
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
