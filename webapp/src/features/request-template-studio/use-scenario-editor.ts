import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RequestStudioApiError } from "./api";
import { archiveScenario, createScenario, fetchScenarioDetail, saveScenario, type ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

function blankScenario(): ScenarioDraftDefinition { return { schema_version: 1, scenario_key: `scenario_${crypto.randomUUID().replaceAll("-", "")}`, title: "Новый сценарий", description: "", service_code: "", offering_full_code: "", category_id: null, entry_block_id: null, blocks: [], process_binding: { request_template_key: "" } }; }
export function useScenarioEditor(autosaveEnabled = false, mapFirst = false) {
  const cache = useQueryClient();
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [definition, setDefinition] = useState<ScenarioDraftDefinition | null>(() => mapFirst ? blankScenario() : null);
  const pristine = useRef<ScenarioDraftDefinition | null>(definition);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [loading, setLoading] = useState(false);
  const requestSequence = useRef(0);
  const saveSequence = useRef(0);
  const latestDefinition = useRef(definition);
  latestDefinition.current = definition;
  const [loadId, setLoadId] = useState<string | null>(null);
  const dirty = !!definition && (detail ? JSON.stringify(definition) !== JSON.stringify(detail.draft.definition) : !mapFirst || JSON.stringify(definition) !== JSON.stringify(pristine.current));
  function accept(value: ScenarioDetail) { setDetail(value); setDefinition(value.draft.definition); setConflict(false); setError(""); cache.setQueryData(["scenario-detail", value.scenario.id], value); }
  const save = useMutation({ mutationFn: async () => {
    if (!definition) throw new Error("Нет черновика");
    const snapshot = definition;
    const sequence = requestSequence.current;
    saveSequence.current = sequence;
    const value = await (detail ? saveScenario(detail.scenario.id, snapshot, detail.draft.revision) : createScenario(snapshot));
    return { value, snapshot, sequence };
  }, onSuccess: async ({ value, snapshot, sequence }) => {
    if (sequence !== requestSequence.current) return;
    setDetail(value); setConflict(false); setError("");
    if (JSON.stringify(latestDefinition.current) === JSON.stringify(snapshot)) setDefinition(value.draft.definition);
    cache.setQueryData(["scenario-detail", value.scenario.id], value);
    setMessage(`Черновик сохранён. Ревизия ${value.draft.revision}.`); await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }, onError: value => {
    if (saveSequence.current !== requestSequence.current) return;
    const isConflict = value instanceof RequestStudioApiError && value.status === 409;
    setConflict(isConflict); setMessage(""); setError(isConflict ? "Черновик изменён другим администратором. Локальные изменения сохранены в редакторе; загрузка серверной версии заменит их." : "Черновик не сохранён. Проверьте название, услугу и настройки, затем повторите.");
  } });
  useEffect(() => {
    if (!autosaveEnabled || !detail || detail.scenario.archived || !dirty || loading || save.isPending || conflict || error || !definition?.title.trim() || !definition.offering_full_code) return;
    const timer = setTimeout(() => save.mutate(), 1200);
    return () => clearTimeout(timer);
  }, [autosaveEnabled, detail, definition, dirty, loading, save.isPending, conflict, error]);
  const archive = useMutation({ mutationFn: async () => {
    if (!detail) throw new Error("Нет черновика");
    return archiveScenario(detail.scenario.id, detail.draft.revision);
  }, onSuccess: async value => { accept(value); setMessage("Сценарий архивирован."); await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }, onError: () => setError("Не удалось архивировать сценарий. Обновите серверную версию и повторите.") });
  async function open(id: string) {
    const sequence = ++requestSequence.current;
    setLoadId(id);
    setLoading(true); setError(""); setMessage("");
    try { const value = await fetchScenarioDetail(id); if (sequence === requestSequence.current) accept(value); }
    catch { if (sequence === requestSequence.current) setError("Не удалось загрузить сценарий. Повторите загрузку."); }
    finally { if (sequence === requestSequence.current) setLoading(false); }
  }
  function create(copy?: ScenarioDraftDefinition, asCopy = true) {
    requestSequence.current += 1; setLoadId(null); setLoading(false);
    setDetail(null); setMessage(""); setError(""); setConflict(false);
    const next = copy ? { ...structuredClone(copy), scenario_key: `scenario_${crypto.randomUUID().replaceAll("-", "")}`, title: asCopy ? `${copy.title} — копия` : copy.title } : blankScenario();
    pristine.current = copy ? null : next;
    setDefinition(next);
  }
  function close() { if (mapFirst) { create(); return; } requestSequence.current += 1; setLoadId(null); setLoading(false); setDefinition(null); setDetail(null); setError(""); setMessage(""); setConflict(false); }
  function change(value: ScenarioDraftDefinition) { setDefinition(value); setMessage(""); }
  return { definition, detail, dirty, message, error, conflict, loading, loadId, save, archive, open, create, close, change, accept, busy: loading || save.isPending || archive.isPending };
}
