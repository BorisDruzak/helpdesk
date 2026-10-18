import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { updateAdminRegistryPerson } from "../api";

type OrganizationField = {
  key: string; label: string; state: string; value?: string | null;
  currentLabel?: string | null; pendingLabel?: string | null;
  pending?: { proposal_id: string; value: string };
};

export function RegistryOrganizationReview({ personId, fields }: { personId: string; fields: OrganizationField[] }) {
  const client = useQueryClient();
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: async ({ field, decision }: { field: OrganizationField; decision: "approve" | "reject" | "confirm" }) => {
      await updateAdminRegistryPerson(personId, decision === "confirm"
        ? { [field.key]: field.value, reason: reason.trim() }
        : { reason: reason.trim(), organization_review: { field: field.key, proposal_id: field.pending!.proposal_id, decision } });
    },
    onSuccess: async () => { setReason(""); await client.invalidateQueries({ queryKey: ["admin-registry"] }); },
  });
  return <section className="space-y-3 border-t border-border pt-4" aria-label="Проверка организационных сведений">
    <h3 className="text-sm font-semibold">Организационные сведения</h3>
    <p className="text-xs text-slate-500">Подтверждение учётной записи не подтверждает подразделение и локацию. Решение изменяет официальный контекст и записывается в историю Registry.</p>
    <label className="block text-sm">Причина решения<Input value={reason} onChange={event => setReason(event.target.value)} /></label>
    {fields.map(field => <div className="rounded-md border border-border p-3 text-sm" key={field.key}>
      <p className="font-semibold">{field.label}</p>
      <p>{field.currentLabel || "Не указано"}</p>
      <p className="text-xs text-slate-500">{field.state === "confirmed" ? "Подтверждено организацией" : field.state === "self_reported" ? "Указано сотрудником" : "Исторические сведения: источник не подтверждён"}</p>
      {field.pending ? <>
        <p className="mt-2">Предложено: {field.pendingLabel || "Справочник недоступен"}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button type="button" disabled={!reason.trim() || mutation.isPending} aria-label={`Подтвердить изменение ${field.key === "department_id" ? "подразделения" : "локации"}`} onClick={() => mutation.mutate({ field, decision: "approve" })}>Подтвердить</Button>
          <Button type="button" variant="outline" disabled={!reason.trim() || mutation.isPending} aria-label={`Отклонить изменение ${field.key === "department_id" ? "подразделения" : "локации"}`} onClick={() => mutation.mutate({ field, decision: "reject" })}>Отклонить</Button>
        </div>
      </> : field.state !== "confirmed" && field.value ? <Button className="mt-2" type="button" variant="outline" disabled={!reason.trim() || mutation.isPending} onClick={() => mutation.mutate({ field, decision: "confirm" })}>Подтвердить текущие сведения: {field.label.toLowerCase()}</Button> : null}
    </div>)}
    {mutation.isError ? <p role="alert" className="text-sm text-rose-700">{mutation.error instanceof Error ? mutation.error.message : "Не удалось сохранить решение"}</p> : null}
    {mutation.isSuccess ? <p role="status" className="text-sm text-emerald-700">Решение сохранено</p> : null}
  </section>;
}
