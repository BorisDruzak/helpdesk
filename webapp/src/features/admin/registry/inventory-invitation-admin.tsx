import { useState, type FormEvent } from "react";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/input";
import { SearchableSelect } from "../../../components/ui/searchable-select";
import { fetchRegistrationOptions, type RegistrationOptions } from "../../auth/requester-registration";
import { useSessionCapabilities } from "../../auth/use-session-capabilities";

type IssuedInvitation = { code: string; expires_at: string; full_name: string };

export function InventoryInvitationAdmin() {
  const capabilities = useSessionCapabilities();
  const [options, setOptions] = useState<RegistrationOptions | null>(null);
  const [inventoryId, setInventoryId] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [reason, setReason] = useState("");
  const [issued, setIssued] = useState<IssuedInvitation | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadDepartments() {
    setError("");
    try {
      setOptions(await fetchRegistrationOptions());
    } catch {
      setError("Не удалось загрузить отделы.");
    }
  }

  async function issue(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    setIssued(null);
    try {
      const response = await fetch("/api/web/admin/registry/inventory-invitations", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ inventory_person_id: inventoryId.trim(), department_id: departmentId, reason: reason.trim() }),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.status !== "success") throw Error(payload?.error ?? "Не удалось выдать приглашение.");
      setIssued(payload.data);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось выдать приглашение.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke() {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/web/admin/registry/inventory-invitations/" + encodeURIComponent(inventoryId.trim()), {
        method: "DELETE", credentials: "same-origin", cache: "no-store",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({reason: reason.trim()}),
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok || payload?.status !== "success") throw Error(payload?.error ?? "Не удалось отозвать приглашение.");
      setIssued(null);
      setNotice(payload.data.revoked ? "Приглашение отозвано." : "Действующего приглашения нет.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Не удалось отозвать приглашение.");
    } finally {
      setBusy(false);
    }
  }

  if (!capabilities?.inventory_invitation_enabled) return null;
  return (
    <details className="surface-panel mb-4 p-4" onToggle={(event) => {
      if (!event.currentTarget.open) setIssued(null);
    }}>
      <summary className="cursor-pointer font-semibold">Приглашение сотрудника из инвентаризации</summary>
      {!options ? <Button className="mt-3" type="button" variant="outline" onClick={() => void loadDepartments()}>
        Подготовить приглашение
      </Button> : (
        <form className="mt-3" onSubmit={(event) => void issue(event)}>
          <fieldset disabled={busy} className="space-y-3">
            <label className="block space-y-1 text-sm font-medium">ID сотрудника из web_ovpn
              <Input required maxLength={36} value={inventoryId} onChange={(event) => { setInventoryId(event.target.value); setIssued(null); setNotice(""); }} />
            </label>
            <SearchableSelect label="Отдел Helpdesk" required value={departmentId}
              options={options.departments} onChange={setDepartmentId} />
            <label className="block space-y-1 text-sm font-medium">Основание выдачи
              <Input required maxLength={500} value={reason} onChange={(event) => setReason(event.target.value)} />
            </label>
            <Button type="submit" disabled={busy || !departmentId || !inventoryId.trim() || !reason.trim()}>
              Выдать код
            </Button>
            <Button type="button" variant="outline" disabled={busy || !inventoryId.trim() || !reason.trim()}
              onClick={() => void revoke()}>Отозвать приглашение</Button>
          </fieldset>
        </form>
      )}
      {error ? <p role="alert" className="mt-3 text-sm text-rose-700">{error}</p> : null}
      {notice ? <p className="mt-3 text-sm" role="status">{notice}</p> : null}
      {issued ? <div className="mt-3 space-y-2" role="status">
        <p>Приглашение для {issued.full_name}. Действует до {new Date(issued.expires_at).toLocaleTimeString("ru-RU", {hour: "2-digit", minute: "2-digit"})}.</p>
        <label className="block space-y-1 text-sm font-medium">Одноразовый код
          <Input readOnly value={issued.code} onFocus={(event) => event.target.select()} />
        </label>
      </div> : null}
    </details>
  );
}
