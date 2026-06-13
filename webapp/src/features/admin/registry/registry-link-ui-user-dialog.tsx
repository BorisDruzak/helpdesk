import { useEffect, useMemo, useState } from "react";

import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import type { AdminRegistryPayload } from "../api";

type PersonRow = AdminRegistryPayload["people"][number];
type UiUserRow = NonNullable<AdminRegistryPayload["ui_users"]>[number];

export type LinkUiUserDialogState = {
  person: PersonRow;
} | null;

type Props = {
  busy?: boolean;
  state: LinkUiUserDialogState;
  uiUsers: UiUserRow[];
  onClose: () => void;
  onSubmit: (payload: { user_login: string; person_id: string; reason: string }) => void;
};

export function RegistryLinkUiUserDialog({ busy, onClose, onSubmit, state, uiUsers }: Props) {
  const [query, setQuery] = useState("");
  const [userLogin, setUserLogin] = useState("");
  const [reason, setReason] = useState("");
  const candidates = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return uiUsers
      .filter((user) => !user.linked_person_id)
      .filter((user) => !normalized || `${user.user_login} ${user.actor_role}`.toLowerCase().includes(normalized));
  }, [query, uiUsers]);

  useEffect(() => {
    setQuery("");
    setUserLogin("");
    setReason("Связь UI-аккаунта с карточкой реестра");
  }, [state]);

  useEffect(() => {
    if (!userLogin && candidates.length) {
      setUserLogin(candidates[0].user_login);
    }
  }, [candidates, userLogin]);

  if (!state) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/35 p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Связать UI-аккаунт</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-600">
            Карточка: <span className="font-semibold text-slate-950">{state.person.display_name}</span>
          </p>
          <label className="block text-sm font-medium text-slate-700">
            Поиск UI-аккаунта
            <Input
              className="mt-2"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="login, email или роль"
              value={query}
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            UI-аккаунт
            <select
              aria-label="UI-аккаунт"
              className="field-base mt-2 h-11 w-full px-3 text-sm"
              onChange={(event) => setUserLogin(event.target.value)}
              value={userLogin}
            >
              {candidates.length ? candidates.map((user) => (
                <option key={user.user_login} value={user.user_login}>
                  {user.user_login} · {user.actor_role}
                </option>
              )) : <option value="">Нет незалинкованных аккаунтов</option>}
            </select>
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Причина
            <Input
              aria-label="Причина"
              className="mt-2"
              onChange={(event) => setReason(event.target.value)}
              value={reason}
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button onClick={onClose} variant="ghost">Отмена</Button>
            <Button
              disabled={busy || !userLogin || !reason.trim()}
              onClick={() => onSubmit({ user_login: userLogin, person_id: state.person.person_id, reason: reason.trim() })}
            >
              Связать
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
