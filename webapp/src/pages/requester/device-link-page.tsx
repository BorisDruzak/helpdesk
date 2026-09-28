import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { linkRequesterDevice, RequesterApiError } from "../../features/requester/api";
import { clearPendingDeviceCode, normalizeDeviceCode, pendingDeviceCode, rememberPendingDeviceCode } from "../../features/requester/device-link-state";
import { requesterInvalidations, useRequesterProfileQuery } from "../../features/requester/queries";

// Requester wizard: obtain code -> submit proof -> ownership result.
export function RequesterDeviceLinkPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const profileQuery = useRequesterProfileQuery();
  const [code, setCode] = useState(pendingDeviceCode);
  const [error, setError] = useState<string | null>(null);
  const [pendingReview, setPendingReview] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const setupPath = "/app/requester/profile/setup?next=%2Fapp%2Frequester%2Fdevices%2Flink";

  async function submit(event: FormEvent) {
    event.preventDefault();
    const normalized = normalizeDeviceCode(code);
    if (!normalized) { setError("Введите шестизначный код в формате 123-456."); return; }
    setSubmitting(true);
    setError(null);
    try {
      const result = await linkRequesterDevice(normalized);
      clearPendingDeviceCode();
      setCode("");
      await requesterInvalidations.afterDeviceLink(queryClient);
      if (result.binding_status === "pending_admin_review") setPendingReview(true);
      else navigate("/app/requester/devices", { replace: true });
    } catch (failure) {
      if (failure instanceof RequesterApiError && failure.code === "REQUESTER_PROFILE_INCOMPLETE") {
        rememberPendingDeviceCode(code);
        navigate(setupPath);
      } else {
        setError(failure instanceof RequesterApiError ? failure.message : "Не удалось привязать устройство. Повторите попытку.");
      }
    } finally { setSubmitting(false); }
  }

  return <section className="mx-auto max-w-xl space-y-5">
    <header className="surface-panel p-5">
      <p className="workspace-boot__eyebrow">Мои устройства</p>
      <h1 className="mt-2 text-2xl font-semibold text-slate-950">Привязать компьютер</h1>
      <p className="mt-3 text-sm leading-6 text-slate-600">Откройте Endpoint Agent в области уведомлений → «Привязать компьютер к Helpdesk». Введите показанный код.</p>
    </header>
    <div className="surface-panel p-5">
      {profileQuery.isLoading ? <p role="status">Проверяем профиль…</p> : profileQuery.error ?
        <p role="alert">Не удалось проверить профиль. <button type="button" onClick={() => void profileQuery.refetch()}>Повторить</button></p> : pendingReview ?
        <div role="status" className="space-y-4"><p>Этот компьютер уже связан с другим пользователем или требует проверки. Запрос на изменение владельца отправлен администратору.</p><Link to="/app/requester/devices">Мои устройства</Link></div> :
        !profileQuery.data?.profile || profileQuery.data.profile_completion?.complete === false ?
          <div className="space-y-4"><p>Заполните профиль, чтобы привязать устройство.</p><Link className="font-semibold text-brand-700" to={setupPath}>Заполнить профиль</Link></div> :
          <form onSubmit={submit} className="space-y-4">
            <label className="block space-y-2"><span>Код привязки</span><Input name="code" inputMode="numeric" autoComplete="off" maxLength={7} placeholder="123-456" value={code} onChange={(event) => { setCode(event.target.value); rememberPendingDeviceCode(event.target.value); }} /></label>
            <p className="text-sm text-slate-600">Код действует 10 минут и используется один раз.</p>
            {error ? <p role="alert" className="text-sm text-rose-700">{error}</p> : null}
            <Button type="submit" disabled={submitting}>{submitting ? "Проверяем…" : "Привязать устройство"}</Button>
          </form>}
    </div>
    <Link className="text-sm font-semibold text-brand-700" to="/app/requester/devices" onClick={clearPendingDeviceCode}>Отмена</Link>
  </section>;
}
