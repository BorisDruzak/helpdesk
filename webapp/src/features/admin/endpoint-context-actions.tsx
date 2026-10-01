import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { Select } from "../../components/ui/select";
import { fetchEndpointCollection, fetchEndpointHistory, compareEndpointHistory, refreshEndpointContext, endpointErrorText } from "./endpoint-context-api";
import type { EndpointContextCollection, SafeContextProfile } from "./endpoint-context-types";
import { contextDate } from "./endpoint-context-view";
import { ContextSnapshotContent } from "./endpoint-profile-content";

const labels: Record<SafeContextProfile, string> = { baseline_v1: "Базовый контекст / ПО", inventory_v1: "Оборудование", health_v1: "Здоровье", network_v1: "Сеть", session_v1: "Сессия" };
const statusLabels: Record<EndpointContextCollection["status"], string> = { requested: "Запрошено", queued: "В очереди", delivered: "Доставлено", collecting: "Сбор данных", result_received: "Результат получен", validated: "Проверено", completed: "Завершено", failed: "Ошибка", expired: "Истекло время ожидания" };
const terminal = new Set(["completed", "failed", "expired"]);

function CollectionStatus({ initial, deviceId }: { initial: EndpointContextCollection; deviceId: string }) {
  const cache = useQueryClient();
  const [started, setStarted] = useState(() => Date.now());
  const [waitExpired, setWaitExpired] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setWaitExpired(true), 120_000);
    return () => clearTimeout(timer);
  }, [started]);
  const status = useQuery({ queryKey: ["endpoint-collection", initial.id], queryFn: ({ signal }) => fetchEndpointCollection(initial.id, signal), retry: false,
    refetchInterval: query => query.state.error || terminal.has(query.state.data?.collection.status ?? initial.status) || waitExpired || Date.now() - started >= 120_000 ? false : 1500 });
  const collection = status.data?.collection ?? initial;
  useEffect(() => {
    if (collection.status === "completed") void Promise.all([
      cache.invalidateQueries({queryKey: ["endpoint-device", deviceId]}), cache.invalidateQueries({queryKey: ["endpoint-fleet"]}), cache.invalidateQueries({queryKey: ["endpoint-history", deviceId]}),
    ]);
  }, [cache, deviceId, collection.id, collection.status]);
  return <li className="rounded-xl border border-border p-3"><strong>{labels[collection.profile]}</strong> · {status.isError ? "Статус неизвестен" : statusLabels[collection.status]}
    {collection.failure_code && <p className="text-sm text-amber-800">Код ошибки Endpoint: {collection.failure_code}</p>}
    {status.isError && <p className="text-sm text-amber-800">{endpointErrorText(status.error)}</p>}
    {!terminal.has(collection.status) && (waitExpired || Date.now() - started >= 120_000) && <p className="text-sm text-slate-500">Ожидание в браузере приостановлено; результат Endpoint ещё не подтверждён.</p>}
    {(status.isError || (!terminal.has(collection.status) && (waitExpired || Date.now() - started >= 120_000))) && <Button size="sm" variant="outline" onClick={() => { setWaitExpired(false); setStarted(Date.now()); void status.refetch(); }}>Проверить статус</Button>}
  </li>;
}
export function EndpointContextRefresh({ deviceId }: { deviceId: string }) {
  const [profiles, setProfiles] = useState<SafeContextProfile[]>(Object.keys(labels) as SafeContextProfile[]);
  const refresh = useMutation({ mutationFn: () => refreshEndpointContext(deviceId, profiles), retry: false });
  return <div className="space-y-4 rounded-panel border border-border bg-white p-5"><h2 className="font-semibold">Обновить данные</h2><div className="flex flex-wrap gap-4">{Object.entries(labels).map(([profile, label]) => <label className="flex items-center gap-2 text-sm" key={profile}><input type="checkbox" checked={profiles.includes(profile as SafeContextProfile)} disabled={refresh.isPending} onChange={event => setProfiles(previous => event.target.checked ? [...previous, profile as SafeContextProfile] : previous.filter(item => item !== profile))}/>{label}</label>)}</div><Button disabled={!profiles.length || refresh.isPending} onClick={() => refresh.mutate()}>{refresh.isPending ? "Запрашиваем…" : "Запросить обновление"}</Button>
    {refresh.isError && <p role="alert">{endpointErrorText(refresh.error)}</p>}{refresh.data && <div role="status"><p className="mb-3 text-sm">{refresh.data.status === "partial" ? "Часть запросов не принята. Проверьте результат каждого профиля." : refresh.data.status === "failed" ? "Запросы не приняты." : "Запросы приняты. Ожидаем результаты Endpoint."}</p><ul className="space-y-2">{refresh.data.results.map(result => result.collection ? <CollectionStatus key={result.collection.id} initial={result.collection} deviceId={deviceId}/> : <li key={result.profile} className="rounded-xl bg-amber-50 p-3">{labels[result.profile]} · Запрос не принят: {result.error_code}</li>)}</ul></div>}
  </div>;
}
export function EndpointContextHistory({ deviceId }: { deviceId: string }) {
  const [profile, setProfile] = useState<"baseline_v1" | "inventory_v1">("inventory_v1");
  const [before, setBefore] = useState("");
  const [after, setAfter] = useState("");
  const history = useQuery({ queryKey: ["endpoint-history", deviceId, profile], queryFn: ({ signal }) => fetchEndpointHistory(deviceId, profile, signal), retry: false });
  const compare = useMutation({ mutationFn: () => compareEndpointHistory(deviceId, before, after), retry: false });
  const snapshots = history.data?.snapshots ?? [];
  return <div className="space-y-5"><Select aria-label="Профиль истории" value={profile} onChange={event => { setProfile(event.target.value as typeof profile); setBefore(""); setAfter(""); compare.reset(); }}><option value="inventory_v1">Оборудование</option><option value="baseline_v1">Базовый контекст / ПО</option></Select>
    {history.isPending && <p>Загрузка истории…</p>}{history.isError && <p role="alert">{endpointErrorText(history.error)}</p>}{history.isSuccess && !snapshots.length && <p>Исторических наблюдений этого профиля пока нет.</p>}
    {snapshots.length >= 2 && <div className="grid items-end gap-3 md:grid-cols-3">{([["Исходное наблюдение", before, setBefore], ["Новое наблюдение", after, setAfter]] as const).map(([label, value, change]) => <label key={label} className="text-sm">{label}<Select aria-label={label} disabled={compare.isPending} value={value} onChange={event => { change(event.target.value); compare.reset(); }}><option value="">Выберите наблюдение</option>{snapshots.map(snapshot => <option value={snapshot.id} key={snapshot.id}>{contextDate(snapshot.collected_at)}</option>)}</Select></label>)}<Button disabled={!before || !after || before === after || compare.isPending} onClick={() => compare.mutate()}>Сравнить</Button></div>}
    {compare.isError && <p role="alert">{endpointErrorText(compare.error)}</p>}{compare.data && <div role="status">{compare.data.changes.length ? <ul>{compare.data.changes.map((change, index) => <li key={index}>{change.summary}</li>)}</ul> : <p>Семантических изменений нет.</p>}</div>}
    {snapshots.map(snapshot => <details className="rounded-xl border border-border p-4" key={snapshot.id}><summary className="cursor-pointer text-sm font-medium">{contextDate(snapshot.collected_at)} · {snapshot.id}</summary><div className="mt-4"><ContextSnapshotContent snapshot={snapshot}/></div></details>)}
  </div>;
}
