import { Save, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../../components/ui/card";
import { Input } from "../../../components/ui/input";
import { fetchAdminRegistryPolicies, updateAdminRegistryPolicies, type AdminRegistryPolicyPayload } from "../api";

function clonePolicies(value: AdminRegistryPolicyPayload["effective"]): AdminRegistryPolicyPayload["effective"] {
  return JSON.parse(JSON.stringify(value)) as AdminRegistryPolicyPayload["effective"];
}

export function RegistryPoliciesTab() {
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["admin-registry-policies"], queryFn: fetchAdminRegistryPolicies, retry: false });
  const [draft, setDraft] = useState<AdminRegistryPolicyPayload["effective"] | null>(null);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (query.data?.effective) {
      setDraft(clonePolicies(query.data.effective));
    }
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: async () => {
      if (!draft) return;
      await updateAdminRegistryPolicies({ policies: draft, reason });
    },
    onSuccess: async () => {
      setReason("");
      await queryClient.invalidateQueries({ queryKey: ["admin-registry-policies"] });
      await queryClient.invalidateQueries({ queryKey: ["admin-registry"] });
    },
  });

  if (query.isLoading || !draft) {
    return <p className="text-sm text-slate-500">Загружаем политики...</p>;
  }

  const setRegistration = (key: keyof typeof draft.registration, value: boolean | number) => {
    setDraft({ ...draft, registration: { ...draft.registration, [key]: value } });
  };
  const setAccount = (key: keyof typeof draft.account_sessions, value: boolean | number | null) => {
    setDraft({ ...draft, account_sessions: { ...draft.account_sessions, [key]: value } });
  };
  const setTicket = (key: keyof typeof draft.ticket_visibility, value: boolean) => {
    setDraft({ ...draft, ticket_visibility: { ...draft.ticket_visibility, [key]: value } });
  };

  return (
    <div className="space-y-4">
      {mutation.error ? <p className="text-sm text-rose-600">{mutation.error instanceof Error ? mutation.error.message : "Не удалось сохранить политики"}</p> : null}
      {draft.warnings ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {Object.values(draft.warnings).join(". ")}
        </div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-3">
        <PolicyCard title="Registration">
          <CheckRow label="Require user confirmation" value={draft.registration.require_user_confirmation} onChange={(value) => setRegistration("require_user_confirmation", value)} />
          <CheckRow label="Require admin confirmation" value={draft.registration.require_admin_confirmation} onChange={(value) => setRegistration("require_admin_confirmation", value)} />
          <CheckRow label="Auto approve first binding" value={draft.registration.auto_approve_first_binding} onChange={(value) => setRegistration("auto_approve_first_binding", value)} warning />
          <CheckRow label="Allow shared devices" value={draft.registration.allow_shared_devices} onChange={(value) => setRegistration("allow_shared_devices", value)} />
          <CheckRow label="Allow responsible binding" value={draft.registration.allow_responsible_binding} onChange={(value) => setRegistration("allow_responsible_binding", value)} />
          <NumberRow label="Max primary devices" value={draft.registration.max_primary_devices_per_person} onChange={(value) => setRegistration("max_primary_devices_per_person", value)} />
          <NumberRow label="Stale after days" value={draft.registration.stale_after_days} onChange={(value) => setRegistration("stale_after_days", value)} />
        </PolicyCard>
        <PolicyCard title="Account Sessions">
          <NullableNumberRow label="Confirmed binding TTL hours" value={draft.account_sessions.confirmed_binding_ttl_hours} onChange={(value) => setAccount("confirmed_binding_ttl_hours", value)} />
          <NumberRow label="Other account TTL hours" value={draft.account_sessions.verified_other_account_ttl_hours} onChange={(value) => setAccount("verified_other_account_ttl_hours", value)} />
          <NumberRow label="Pending registration TTL hours" value={draft.account_sessions.registration_pending_ttl_hours} onChange={(value) => setAccount("registration_pending_ttl_hours", value)} />
          <CheckRow label="Allow other account login" value={draft.account_sessions.allow_other_account_login} onChange={(value) => setAccount("allow_other_account_login", value)} />
          <CheckRow label="Other account requires reason" value={draft.account_sessions.other_account_requires_reason} onChange={(value) => setAccount("other_account_requires_reason", value)} />
          <CheckRow label="Other account requires admin approval" value={draft.account_sessions.other_account_requires_admin_approval} onChange={(value) => setAccount("other_account_requires_admin_approval", value)} />
          <CheckRow label="Allow on shared/responsible" value={draft.account_sessions.allow_other_account_on_shared_or_responsible} onChange={(value) => setAccount("allow_other_account_on_shared_or_responsible", value)} />
        </PolicyCard>
        <PolicyCard title="Ticket Visibility">
          <CheckRow label="Owner can see historical tickets" value={draft.ticket_visibility.owner_can_see_historical_tickets} onChange={(value) => setTicket("owner_can_see_historical_tickets", value)} />
          <CheckRow label="Other account only own session tickets" value={draft.ticket_visibility.other_account_only_own_session_tickets} onChange={(value) => setTicket("other_account_only_own_session_tickets", value)} />
        </PolicyCard>
      </div>
      <Card>
        <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <Input placeholder="Причина изменения политики" value={reason} onChange={(event) => setReason(event.target.value)} />
          <div className="flex gap-2">
            <Button leadingIcon={<RotateCcw className="h-4 w-4" />} onClick={() => query.data && setDraft(clonePolicies(query.data.effective))} variant="outline">Сбросить</Button>
            <Button disabled={!reason.trim() || mutation.isPending} leadingIcon={<Save className="h-4 w-4" />} onClick={() => mutation.mutate()}>Сохранить</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PolicyCard({ children, title }: { children: ReactNode; title: string }) {
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent className="space-y-3">{children}</CardContent>
    </Card>
  );
}

function CheckRow({ label, onChange, value, warning }: { label: string; value: boolean; onChange: (value: boolean) => void; warning?: boolean }) {
  return (
    <label className="flex items-center justify-between gap-3 rounded-md border border-border px-3 py-2 text-sm">
      <span className="flex items-center gap-2">{label}{warning ? <Badge tone="warning">warning</Badge> : null}</span>
      <input checked={value} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
    </label>
  );
}

function NumberRow({ label, onChange, value }: { label: string; value: number; onChange: (value: number) => void }) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <Input className="mt-2" min={1} onChange={(event) => onChange(Number(event.target.value || 1))} type="number" value={value} />
    </label>
  );
}

function NullableNumberRow({ label, onChange, value }: { label: string; value: number | null; onChange: (value: number | null) => void }) {
  return (
    <label className="block text-sm font-medium">
      {label}
      <Input className="mt-2" onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))} placeholder="null = no expiry" type="number" value={value ?? ""} />
    </label>
  );
}
