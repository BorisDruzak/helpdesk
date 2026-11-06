import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RequestStudioApiError } from "./api";
import { archiveScenario, createScenario, createServiceScenario, fetchScenarioDetail, saveScenario, upgradeScenarioV4, ScenarioApiError, type ScenarioDetail } from "./scenario-api";
import { upgradeScenarioDraft } from "./scenario-v4-model";
import { scenarioIssueText } from "./scenario-issues";
import type { ScenarioAttachment, ScenarioDraftDefinition, ScenarioRichDocument, ScenarioRichNode } from "./scenario-contract";

function semanticJson(value: unknown): string {
  return JSON.stringify(value, (_key, item) => item && typeof item === "object" && !Array.isArray(item)
    ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a.localeCompare(b))) : item);
}
function rebindCopiedMaterials(definition: ScenarioDraftDefinition, rebindings: Record<string, ScenarioAttachment> = {}): ScenarioDraftDefinition {
  if (!Object.keys(rebindings).length) return definition;
  const materials = (items?: ScenarioAttachment[]) => items?.map(item => rebindings[item.asset_id] || item);
  function document(value?: ScenarioRichDocument | null): ScenarioRichDocument | null | undefined {
    const node = (item: ScenarioRichNode): ScenarioRichNode => ({ ...item, ...(item.type === "image" && rebindings[String(item.attrs?.asset_id)] ? { attrs: { ...item.attrs, asset_id: rebindings[String(item.attrs?.asset_id)].asset_id } } : {}), ...(item.content ? { content: item.content.map(node) } : {}) });
    return value ? { ...value, content: value.content.map(node) } : value;
  }
  return { ...definition, blocks: definition.blocks?.map(block => block.kind === "instruction" ? { ...block, content: { ...block.content, attachments: materials(block.content.attachments), ...(block.content.rich_document ? { rich_document: document(block.content.rich_document) } : {}) } } : block.kind === "form_page" ? { ...block, fields: block.fields.map(field => ({ ...field, help_attachments: materials(field.help_attachments), ...(field.help_document ? { help_document: document(field.help_document) } : {}) })) } : block) };
}
function blankScenario(): ScenarioDraftDefinition { return { schema_version: 3, processing: { routes: {}, sla_profiles: {}, defaults: { route: "", sla_profile: "" }, assignment_mode: "last_matching_branch" }, scenario_key: `scenario_${crypto.randomUUID().replaceAll("-", "")}`, title: "Новый сценарий", description: "", service_code: "", offering_full_code: "", category_id: null, entry_block_id: null, blocks: [], process_binding: { request_template_key: "" } }; }
type SaveRequest = { snapshot: ScenarioDraftDefinition; sequence: number; detail: ScenarioDetail | null; copySourceId: string | null };
type SaveResult = { value: ScenarioDetail; snapshot: ScenarioDraftDefinition; sequence: number };
export function useScenarioEditor(autosaveEnabled = false, mapFirst = false) {
  const cache = useQueryClient();
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [definition, setDefinition] = useState<ScenarioDraftDefinition | null>(() => mapFirst ? blankScenario() : null);
  const pristine = useRef<ScenarioDraftDefinition | null>(definition);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [accessError, setAccessError] = useState<"session" | "origin" | "forbidden" | null>(null);
  const [conflict, setConflict] = useState(false);
  const [loading, setLoading] = useState(false);
  const [upgrading, setUpgrading] = useState(false);
  const requestSequence = useRef(0);
  const saveFlight = useRef<{ sequence: number; promise: Promise<SaveResult> } | null>(null);
  const saveFault = useRef<unknown>(null);
  const copySourceId = useRef<string | null>(null);
  const latestDefinition = useRef(definition);
  latestDefinition.current = definition;
  const latestDetail = useRef(detail); latestDetail.current = detail;
  function updateDefinition(value: ScenarioDraftDefinition | null) { latestDefinition.current = value; setDefinition(value); }
  function updateDetail(value: ScenarioDetail | null) { latestDetail.current = value; setDetail(value); }
  const [loadId, setLoadId] = useState<string | null>(null);
  const dirty = !!definition && (detail ? semanticJson(definition) !== semanticJson(detail.draft.definition) : !mapFirst || semanticJson(definition) !== semanticJson(pristine.current));
  function accept(value: ScenarioDetail) { copySourceId.current = null; saveFault.current = null; updateDetail(value); updateDefinition(value.draft.definition); setConflict(false); setError(""); setAccessError(null); cache.setQueryData(["scenario-detail", value.scenario.id], value); }
  const saveMutation = useMutation({ mutationFn: async ({ snapshot, sequence, detail: current, copySourceId: source }: SaveRequest) => {
    const value = await (current ? saveScenario(current.scenario.id, snapshot, current.draft.revision) : snapshot.offering_full_code ? createScenario(snapshot) : createServiceScenario(snapshot, source));
    return { value, snapshot, sequence };
  }, onSuccess: async ({ value, snapshot, sequence }) => {
    if (sequence !== requestSequence.current) return;
    copySourceId.current = null;
    saveFault.current = null; updateDetail(value); setConflict(false); setError(""); setAccessError(null);
    if (semanticJson(latestDefinition.current) === semanticJson(snapshot)) updateDefinition(value.draft.definition);
    else if (!snapshot.offering_full_code && latestDefinition.current) updateDefinition(rebindCopiedMaterials({
      ...latestDefinition.current, offering_full_code: value.draft.definition.offering_full_code,
      service_code: value.draft.definition.service_code,
      schema_version: value.draft.definition.schema_version, publish_offering: value.draft.definition.publish_offering,
      process_binding: { ...latestDefinition.current.process_binding, request_template_key: value.draft.definition.process_binding.request_template_key },
    }, value.asset_rebindings));
    cache.setQueryData(["scenario-detail", value.scenario.id], value);
    setMessage(semanticJson(latestDefinition.current) === semanticJson(value.draft.definition) ? `Черновик сохранён. Ревизия ${value.draft.revision}.` : "Предыдущие изменения сохранены. Новые правки ожидают автосохранения."); await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }, onError: (value, request) => {
    if (request.sequence !== requestSequence.current) return;
    saveFault.current = value;
    const code = value instanceof RequestStudioApiError ? value.errorCode : undefined;
    const refusal = value instanceof RequestStudioApiError ? value.status === 401 ? "session" : value.status === 403 ? code?.startsWith("CSRF_") ? "origin" : "forbidden" : null : null;
    setAccessError(refusal);
    const isConflict = code === "REVISION_CONFLICT";
    const reasons: Record<string, string> = {
      SERVICE_PROCESSING_DEFAULT_REQUIRED: "Для раздела не определена обработка новых услуг. Укажите настройки обработки по умолчанию в разделе каталога.",
      CONSTRAINT_CONFLICT: "Проверьте связи с каталогом: связанный объект удалён или такое значение уже существует.",
      CATALOG_BINDING_INVALID: "Раздел, услуга и тип обращения не соответствуют друг другу. Проверьте назначение сценария.",
      CATALOG_BINDING_IMMUTABLE: "Нельзя изменить привязку сохранённого сценария к разделу или услуге.",
      CATEGORY_BINDING_INVALID: "Категория недоступна или принадлежит другому разделу. Выберите категорию в разделе сценария.",
      SERVICE_NOT_FOUND: "Раздел каталога не найден. Выберите существующий раздел.",
      OFFERING_NOT_FOUND: "Услуга каталога не найдена. Обновите каталог.",
      TEMPLATE_NOT_FOUND: "Тип обращения не найден. Выберите существующий тип.",
      PAYLOAD_TOO_LARGE: "Размер карты превышает 1 МБ. Сократите текст или число шагов.",
      CSRF_ORIGIN_MISMATCH: "Сервер отклонил адрес страницы. Проверьте, что Студия открыта по правильному адресу; администратору нужно проверить внешний адрес сервера. Не перезагружайте вкладку с правками.",
      CSRF_ORIGIN_REQUIRED: "Сервер не получил адрес страницы для проверки сохранения. Проверьте настройки браузера и адрес Студии. Не перезагружайте вкладку с правками.",
    };
    const issues = value instanceof ScenarioApiError ? value.issues : [];
    const reason = issues.length ? issues.map(issue => scenarioIssueText(issue, latestDefinition.current ?? undefined)).join("\n")
      : reasons[code ?? ""] ?? (refusal === "session" ? "Сессия входа завершилась. Войдите в той же учётной записи в отдельной вкладке, затем проверьте вход и сохраните здесь. Не перезагружайте эту вкладку." : refusal === "forbidden" ? "Недостаточно прав для сохранения. Проверьте, что выполнен вход в ту же учётную запись администратора." : value instanceof RequestStudioApiError ? value.status >= 500 ? "Сервер не смог сохранить карту. Повторите сохранение позже." : `Сервер отклонил сохранение (${code || `HTTP ${value.status}`}).` : "Нет ответа от сервера. Проверьте соединение и повторите сохранение.");
    setConflict(isConflict); setMessage(""); setError(isConflict ? "Черновик изменён другим администратором. Локальные изменения сохранены в редакторе; загрузка серверной версии заменит их." : `Черновик не сохранён. ${reason}\nЛокальные изменения остаются в редакторе.`);
  } });
  function saveOnce(): Promise<SaveResult> {
    const sequence = requestSequence.current;
    if (saveFlight.current?.sequence === sequence) return saveFlight.current.promise;
    const snapshot = latestDefinition.current;
    if (!snapshot) return Promise.reject(new Error("Нет черновика"));
    saveFault.current = null;
    const pending = { sequence, promise: null as unknown as Promise<SaveResult> };
    pending.promise = saveMutation.mutateAsync({ snapshot, sequence, detail: latestDetail.current, copySourceId: copySourceId.current }).finally(() => { if (saveFlight.current === pending) saveFlight.current = null; });
    saveFlight.current = pending;
    return pending.promise;
  }
  const save = { ...saveMutation, mutate: () => { void saveOnce().catch(() => {}); }, mutateAsync: saveOnce };
  async function ensureSaved(): Promise<ScenarioDetail> {
    const sequence = requestSequence.current;
    if (saveFlight.current?.sequence === sequence) await saveFlight.current.promise;
    if (sequence !== requestSequence.current) throw new Error("Открыта другая карта. Повторите действие в нужной карте.");
    if (saveFault.current || conflict || accessError || latestDetail.current?.scenario.archived) throw new Error("Сначала устраните ошибку сохранения черновика.");
    const current = latestDefinition.current, saved = latestDetail.current;
    if (!current?.title.trim() || !current.service_code) throw new Error("Укажите название услуги и раздел каталога.");
    if (saved && semanticJson(current) === semanticJson(saved.draft.definition)) return saved;
    const result = await saveOnce();
    if (sequence !== requestSequence.current) throw new Error("Открыта другая карта. Повторите действие в нужной карте.");
    return result.value;
  }
  useEffect(() => {
    if (!autosaveEnabled || detail?.scenario.archived || !dirty || loading || save.isPending || conflict || error || !definition?.title.trim() || !definition.service_code) return;
    const timer = setTimeout(() => save.mutate(), 1200);
    return () => clearTimeout(timer);
  }, [autosaveEnabled, detail, definition, dirty, loading, save.isPending, conflict, error]);
  const archive = useMutation({ mutationFn: async () => {
    if (!detail) throw new Error("Нет черновика");
    return archiveScenario(detail.scenario.id, detail.draft.revision);
  }, onSuccess: async value => { accept(value); setMessage("Сценарий архивирован."); await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }, onError: () => setError("Не удалось архивировать сценарий. Обновите серверную версию и повторите.") });
  async function enableV4() {
    if (!definition || upgrading || save.isPending || accessError) return;
    if (!detail) { change(upgradeScenarioDraft(definition)); return; }
    const sequence = requestSequence.current;
    setUpgrading(true);
    let upgradingOnServer = false;
    try {
      const current = dirty ? (await save.mutateAsync()).value : detail;
      if (sequence !== requestSequence.current) return;
      upgradingOnServer = true;
      const upgraded = await upgradeScenarioV4(current.scenario.id, current.draft.revision);
      if (sequence === requestSequence.current) { accept(upgraded); setMessage("Новые возможности карты включены. Прежние правила услуги сохранены; опубликованная версия не менялась."); }
    } catch (failure) {
      if (sequence === requestSequence.current && upgradingOnServer) setError(failure instanceof RequestStudioApiError && failure.status === 409 ? "Карта изменилась на сервере. Сохраните или загрузите актуальный черновик перед включением новых возможностей." : "Не удалось включить новые возможности. Исходная карта и локальные правки сохранены.");
    } finally { if (sequence === requestSequence.current) setUpgrading(false); }
  }
  async function open(id: string) {
    copySourceId.current = null;
    const sequence = ++requestSequence.current;
    setLoadId(id);
    setLoading(true); setError(""); setMessage(""); setAccessError(null);
    try { const value = await fetchScenarioDetail(id); if (sequence === requestSequence.current) accept(value); }
    catch { if (sequence === requestSequence.current) setError("Не удалось загрузить сценарий. Повторите загрузку."); }
    finally { if (sequence === requestSequence.current) setLoading(false); }
  }
  function create(copy?: ScenarioDraftDefinition, asCopy = true) {
    copySourceId.current = copy && asCopy ? detail?.scenario.id ?? null : null;
    requestSequence.current += 1; setLoadId(null); setLoading(false);
    updateDetail(null); saveFault.current = null; setMessage(""); setError(""); setConflict(false); setAccessError(null);
    const next = copy ? { ...structuredClone(copy), ...(asCopy ? { schema_version: copy.schema_version === 4 ? 4 as const : copy.schema_version === 3 ? 3 as const : 2 as const, offering_full_code: "", process_binding: { ...copy.process_binding, request_template_key: "" } } : {}), scenario_key: `scenario_${crypto.randomUUID().replaceAll("-", "")}`, title: asCopy ? `${copy.title} — копия` : copy.title } : blankScenario();
    pristine.current = copy ? null : next;
    updateDefinition(next);
  }
  function close() { if (mapFirst) { create(); return; } copySourceId.current = null; requestSequence.current += 1; setLoadId(null); setLoading(false); updateDefinition(null); updateDetail(null); saveFault.current = null; setError(""); setMessage(""); setConflict(false); }
  function change(value: ScenarioDraftDefinition) { updateDefinition(value); setMessage(""); }
  return { definition, detail, dirty, message, error, accessError, conflict, loading, upgrading, enableV4, loadId, save, ensureSaved, getDefinition: () => latestDefinition.current, archive, open, create, close, change, accept, busy: loading || upgrading || save.isPending || archive.isPending };
}
