import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { fetchHelpdeskModelRegistry, publishHelpdeskPolicy, type AdminHelpdeskPolicyItem } from "../forms-builder/api";
import { fetchAdminRegistry } from "../admin/api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

export function ScenarioApprovals({ definition, disabled, onChange }: { definition: ScenarioDraftDefinition; disabled: boolean; onChange: (next: ScenarioDraftDefinition) => void }) {
  const latest = useRef({ definition, onChange, disabled });
  latest.current = { definition, onChange, disabled };
  const mounted = useRef(false);
  const generation = useRef(0);
  useEffect(() => { mounted.current = true; generation.current++; return () => { mounted.current = false; generation.current++; }; }, [definition.scenario_key]);
  const registry = useQuery({ queryKey: ["studio-approval-registry"], queryFn: fetchHelpdeskModelRegistry });
  const [editing, setEditing] = useState(false), [confirm, setConfirm] = useState(false), [busy, setBusy] = useState(false);
  const [code, setCode] = useState(""), [title, setTitle] = useState(""), [error, setError] = useState("");
  const [base, setBase] = useState<AdminHelpdeskPolicyItem | null>(null);
  const [config, setConfig] = useState<Record<string, unknown>>({ required: true, approval_mode: "any_one", approver_source: { type: "requester_manager" } });
  const source = config.approver_source && typeof config.approver_source === "object" ? config.approver_source as Record<string, unknown> : {};
  const actors = useQuery({ queryKey: ["studio-approval-actors"], queryFn: fetchAdminRegistry, enabled: editing && source.type === "explicit_users" });
  const policies = registry.data?.policies.approval ?? [];
  const actorChoices = (actors.data?.ui_users ?? []).filter(actor => actor.is_active && ["admin", "support"].includes(actor.actor_role));
  const singleActor = source.user_id || source.approver_id || source.actor_id || source.id;
  const actorList = [source.users, source.user_ids, source.approver_ids, source.actors, source.actor_ids].find(value => Array.isArray(value) && value.length) as unknown[] | undefined;
  const configuredActors = singleActor ? [String(singleActor)] : (actorList ?? []).map(value => typeof value === "string" ? value : value && typeof value === "object" ? String((value as Record<string, unknown>).user_id || (value as Record<string, unknown>).approver_id || (value as Record<string, unknown>).actor_id || (value as Record<string, unknown>).id || (value as Record<string, unknown>).login || (value as Record<string, unknown>).value || "") : String(value)).filter(Boolean);
  const explicit = source.type === "explicit_users";
  const invalidActors = explicit && (!configuredActors.length || configuredActors.some(id => !actorChoices.some(actor => actor.user_login === id)));
  function selectActors(user_ids: string[]) {
    const { user_id: _user, users: _users, actor_id: _actor, actor_ids: _actors, actors: _actorObjects, approver_id: _approver, approver_ids: _approvers, id: _id, ...other } = source;
    setConfig({ ...config, approver_source: { ...other, user_ids } }); setConfirm(false);
  }
  function sourceType(value: string) {
    const { user_id: _user, user_ids: _users, users: _aliases, actor_id: _actor, actor_ids: _actors, actors: _actorObjects, approver_id: _approver, approver_ids: _approvers, id: _id, group_id: _group, code: _code, field: _field, field_key: _fieldKey, ...other } = source;
    setConfig({ ...config, approver_source: { ...other, type: value, ...(value === "explicit_users" ? { user_ids: [] } : {}) } }); setConfirm(false);
  }
  const selected = definition.process_binding.policy_refs?.approval ?? "";
  function choose(value: string) { if (!mounted.current || latest.current.disabled) return; const current = latest.current.definition; const refs = { ...current.process_binding.policy_refs }; if (value) refs.approval = value; else delete refs.approval; latest.current.onChange({ ...current, process_binding: { ...current.process_binding, policy_refs: refs } }); }
  function edit(policy?: AdminHelpdeskPolicyItem) { setBase(policy ?? null); setCode(policy?.code ?? `approval_${crypto.randomUUID().replaceAll("-", "")}`); setTitle(policy?.title ?? "Новое согласование"); setConfig(policy ? structuredClone(policy.config) : { required: true, approval_mode: "any_one", approver_source: { type: "requester_manager" } }); setEditing(true); setConfirm(false); setError(""); }
  async function publish() {
    const operation = generation.current;
    const current = () => mounted.current && generation.current === operation;
    setBusy(true); setError("");
    try {
      const result = await publishHelpdeskPolicy({ kind: "approval", code, title, description: base?.description, scope_level: base?.scope_level ?? "global", scope_ref: base?.scope_ref, config });
      if (!current()) return;
      await registry.refetch();
      if (!current()) return;
      choose(result.policy.code); setEditing(false); setConfirm(false);
    } catch { if (current()) setError("Схема не опубликована. Проверьте параметры и повторите."); }
    finally { if (current()) setBusy(false); }
  }
  return <section aria-label="Согласования" className="grid min-w-0 gap-4 rounded-xl border bg-white p-5"><h2 className="text-xl font-semibold">Согласования</h2><p>Доверенный серверный источник определяет согласующих; решения проходят действующий жизненный цикл обращения.</p>
    {registry.isPending ? <p role="status">Загрузка схем согласования…</p> : registry.isError ? <div role="alert">Не удалось загрузить схемы.<Button onClick={() => void registry.refetch()}>Повторить</Button></div> : <><label>Схема для карты<select className="field-base block w-full" disabled={disabled || busy} value={selected} onChange={event => choose(event.target.value)}><option value="">Наследовать из услуги и шаблона</option>{selected && !policies.some(policy => policy.code === selected && policy.is_active && policy.published_at) && <option value={selected}>Выбранная схема недоступна</option>}{policies.filter((policy, index, all) => policy.is_active && policy.published_at && all.findIndex(other => other.code === policy.code && other.is_active && other.published_at) === index).map(policy => <option key={policy.code} value={policy.code}>{policy.title}</option>)}</select></label><div className="flex flex-wrap gap-2"><Button disabled={disabled || busy} onClick={() => edit()}>Создать схему согласования</Button>{selected && <Button disabled={disabled || busy} variant="outline" onClick={() => edit(policies.find(policy => policy.code === selected))}>Новая версия схемы</Button>}</div></>}
    {editing && <fieldset disabled={disabled || busy} className="grid gap-3"><label>Название<input className="field-base block w-full" value={title} onChange={event => { setTitle(event.target.value); setConfirm(false); }} /></label><label>Источник согласующего<select className="field-base block w-full" value={String(source.type ?? "requester_manager")} onChange={event => { sourceType(event.target.value); }}>{!["requester_manager", "service_owner", "queue_lead", "explicit_users"].includes(String(source.type)) && <option value={String(source.type)}>Существующий источник: {String(source.type)}</option>}<option value="requester_manager">Руководитель заявителя</option><option value="service_owner">Владелец сервиса</option><option value="queue_lead">Руководитель очереди</option><option value="explicit_users">Выбранные согласующие</option></select></label>{explicit && <section aria-label="Выбранные согласующие" className="grid gap-2"><p className="text-sm">Выберите действующие учётные записи поддержки или администраторов. Права на решение и доступ к обращению проверяет сервер.</p>{actors.isPending ? <p role="status">Загрузка согласующих…</p> : actors.isError ? <div role="alert">Не удалось загрузить согласующих.<Button onClick={() => void actors.refetch()}>Повторить загрузку согласующих</Button></div> : <>{actorChoices.map(actor => <label key={actor.user_login} className="flex gap-2"><input type="checkbox" checked={configuredActors.includes(actor.user_login)} onChange={event => { const selected = event.target.checked ? [...configuredActors, actor.user_login] : configuredActors.filter(id => id !== actor.user_login); selectActors(selected); }} />{actor.linked_person_name || actor.user_login}</label>)}{configuredActors.filter(id => !actorChoices.some(actor => actor.user_login === id)).map(id => <label key={id} className="flex gap-2 text-amber-800"><input type="checkbox" checked onChange={() => { selectActors(configuredActors.filter(value => value !== id)); }} />Существующий согласующий недоступен</label>)}{invalidActors && <p role="alert">Выберите хотя бы одного доступного согласующего; недоступные привязки сохраняются до явного удаления.</p>}</>}</section>}<label>Режим согласования<select className="field-base block w-full" value={String(config.approval_mode ?? "any_one")} onChange={event => { setConfig({ ...config, approval_mode: event.target.value }); setConfirm(false); }}><option value="any_one">Достаточно одного</option><option value="all">Все согласующие</option><option value="sequential">Последовательно</option></select></label><details><summary>Расширенные настройки</summary><p>Ключ: {code}</p><p>Дополнительные параметры существующей схемы сохраняются.</p></details>{confirm ? <div role="alert"><p>Опубликовать схему «{title}» в реестре политик Helpdesk? Это действие не публикует карту сценария.</p><Button disabled={!title.trim() || invalidActors} onClick={() => void publish()}>Подтвердить публикацию схемы</Button><Button variant="ghost" onClick={() => setConfirm(false)}>Отмена</Button></div> : <Button disabled={!title.trim() || invalidActors} onClick={() => setConfirm(true)}>Опубликовать схему</Button>}<Button variant="ghost" onClick={() => { setEditing(false); setConfirm(false); }}>Закрыть редактор схемы</Button></fieldset>}{error && <p role="alert">{error}</p>}
  </section>;
}
