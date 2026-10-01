import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { PageHeading } from "../../components/ui/page-heading";
import { Button } from "../../components/ui/button";
import { fetchEndpointDeviceContext, endpointErrorText } from "../../features/admin/endpoint-context-api";
import { ContextFacts, contextBytes, contextDate, RegistryContext } from "../../features/admin/endpoint-context-view";
import { ContextSnapshotContent } from "../../features/admin/endpoint-profile-content";
import { EndpointContextRefresh, EndpointContextHistory } from "../../features/admin/endpoint-context-actions";
import { useSession } from "../../features/auth/session-provider";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
type Tab = "overview" | "system" | "network" | "software" | "health" | "session" | "history" | "registry";
export function AdminDevicePage() {
  const [params] = useSearchParams();
  const id = params.get("device");
  if (!id || !uuidPattern.test(id) || params.getAll("device").length !== 1) return <section className="space-y-4"><h1 className="text-2xl font-semibold">Укажите корректный идентификатор устройства</h1><Link to="/app/admin/inventory">Вернуться к устройствам</Link></section>;
  return <EndpointDeviceDetail key={id} deviceId={id}/>;
}
function EndpointDeviceDetail({ deviceId }: { deviceId: string }) {
  const { session } = useSession();
  const [tab, setTab] = useState<Tab>("overview");
  const context = useQuery({ queryKey: ["endpoint-device", deviceId], queryFn: ({ signal }) => fetchEndpointDeviceContext(deviceId, signal), retry: false });
  const data = context.data;
  const snapshot = (profile: string) => data?.snapshots.find(item => item.profile === profile);
  const system = snapshot("inventory_v1") ?? snapshot("baseline_v1");
  const network = snapshot("network_v1") ?? snapshot("inventory_v1") ?? snapshot("baseline_v1");
  const software = snapshot("baseline_v1"), health = snapshot("health_v1"), currentSession = snapshot("session_v1");
  const tabs: Array<readonly [Tab, string, boolean]> = [["overview", "Обзор", true], ["system", "Система", Boolean(system)], ["network", "Сеть", Boolean(network)], ["software", "ПО", Boolean(software)], ["health", "Здоровье", Boolean(health)], ["session", "Сессия", Boolean(currentSession)], ["history", "История", true], ["registry", "Registry", true]];
  const selectedTab = tabs.some(([name, , available]) => name === tab && available) ? tab : "overview";
  return <section className="space-y-6"><Link className="text-sm text-brand-700" to="/app/admin/inventory">← Устройства</Link><PageHeading eyebrow="Устройство" title={data?.device.display_name ?? "Карточка устройства"} description={deviceId} actions={<Button variant="outline" disabled={context.isFetching} onClick={() => void context.refetch()}>Перечитать карточку</Button>}/>
    {context.isPending && <p role="status">Загрузка контекста Endpoint…</p>}{context.isError && <p className="rounded-panel bg-amber-50 p-5" role="alert">{endpointErrorText(context.error)}</p>}
    {data && !context.isError && <><div className="rounded-panel border border-border bg-white p-5"><ContextFacts rows={[["Статус Endpoint", data.device.online ? "ONLINE" : "OFFLINE"], ["Последнее наблюдение Endpoint", contextDate(data.device.last_seen_at)], ["Идентификатор", data.device.device_identifier], ["Lifecycle Endpoint", data.device.retired_at ? "Выведено из эксплуатации" : "Активное устройство"]]}/></div>
      {session && ["admin", "support"].includes(session.actor_role) && <EndpointContextRefresh deviceId={deviceId}/>}
      <nav aria-label="Контекст устройства" className="flex flex-wrap gap-2">{tabs.filter(([, , available]) => available).map(([name, label]) => <Button key={name} variant={selectedTab === name ? "primary" : "outline"} aria-pressed={selectedTab === name} onClick={() => setTab(name)}>{label}</Button>)}</nav>
      <div className="rounded-panel border border-border bg-white p-5 md:p-6">
        {selectedTab === "overview" && <div className="space-y-5"><h2 className="text-lg font-semibold">Доступные наблюдения</h2>{system && <ContextFacts rows={system.profile === "inventory_v1" ? [["ОС", [system.sections.system.os_name, system.sections.system.os_version].filter(Boolean).join(" ") || null], ["Модель", system.sections.hardware.model], ["CPU", system.sections.hardware.cpu_model], ["RAM", contextBytes(system.sections.memory.total_bytes)]] : system.profile === "baseline_v1" ? [["ОС", system.sections.system.distribution], ["Модель", system.sections.hardware.model], ["CPU", system.sections.hardware.cpu_model], ["RAM", contextBytes(system.sections.hardware.memory_bytes)]] : []}/>} {data.profiles.length ? <ul className="space-y-3">{data.profiles.map(profile => <li key={profile.profile} className="flex flex-wrap justify-between gap-2 rounded-xl bg-slate-50 p-3"><strong className="text-sm">{profile.profile}</strong><span className="text-sm">{profile.status} · {profile.last_collected_at ? contextDate(profile.last_collected_at) : "Не собирался"}</span></li>)}</ul> : <p>Контекст ещё не собран. Запросите нужные профили выше.</p>}<RegistryContext registry={data.registry}/><Link className="block text-brand-700" to="/app/admin/registry">Открыть реестр / оформить привязку</Link></div>}
        {selectedTab === "system" && system && <ContextSnapshotContent snapshot={system} section="system"/>}{selectedTab === "network" && network && <ContextSnapshotContent snapshot={network} section="network"/>}{selectedTab === "software" && software && <ContextSnapshotContent snapshot={software} section="software"/>}{selectedTab === "health" && health && <ContextSnapshotContent snapshot={health}/>}{selectedTab === "session" && currentSession && <><p className="mb-4 text-sm text-slate-500">Наблюдаемый login Endpoint не заменяет активную связь пользователя в Registry.</p><ContextSnapshotContent snapshot={currentSession}/></>}{selectedTab === "history" && <EndpointContextHistory deviceId={deviceId}/>}{selectedTab === "registry" && <div className="space-y-5"><RegistryContext registry={data.registry}/><Link className="text-brand-700" to="/app/admin/registry">Открыть Registry для управления бизнес-контекстом</Link></div>}
      </div></>}
  </section>;
}
