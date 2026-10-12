import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RequestStudioApiError } from "./api";
import { archiveScenario, createScenario, fetchScenarioDetail, saveScenario, type ScenarioDetail } from "./scenario-api";
import type { ScenarioDraftDefinition } from "./scenario-contract";

export function useScenarioEditor() {
  const cache = useQueryClient();
  const [detail, setDetail] = useState<ScenarioDetail | null>(null);
  const [definition, setDefinition] = useState<ScenarioDraftDefinition | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [conflict, setConflict] = useState(false);
  const [loading, setLoading] = useState(false);
  const requestSequence = useRef(0);
  const [loadId, setLoadId] = useState<string | null>(null);
  const dirty = !!definition && (!detail || JSON.stringify(definition) !== JSON.stringify(detail.draft.definition));
  function accept(value: ScenarioDetail) { setDetail(value); setDefinition(value.draft.definition); setConflict(false); setError(""); cache.setQueryData(["scenario-detail", value.scenario.id], value); }
  const save = useMutation({ mutationFn: async () => {
    if (!definition) throw new Error("Нет черновика");
    return detail ? saveScenario(detail.scenario.id, definition, detail.draft.revision) : createScenario(definition);
  }, onSuccess: async value => { accept(value); setMessage(`Черновик сохранён. Ревизия ${value.draft.revision}.`); await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }, onError: value => {
    const isConflict = value instanceof RequestStudioApiError && value.status === 409;
    setConflict(isConflict); setMessage(""); setError(isConflict ? "Черновик изменён другим администратором. Локальные изменения сохранены в редакторе; загрузка серверной версии заменит их." : "Черновик не сохранён. Проверьте название, услугу и настройки, затем повторите.");
  } });
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
    setDefinition(copy ? { ...structuredClone(copy), scenario_key: `scenario_${crypto.randomUUID().replaceAll("-", "")}`, title: asCopy ? `${copy.title} — копия` : copy.title } : {
      schema_version: 1, scenario_key: `scenario_${crypto.randomUUID().replaceAll("-", "")}`, title: "Новый сценарий", description: "", service_code: "", offering_full_code: "", category_id: null, entry_block_id: null, blocks: [], process_binding: { request_template_key: "" },
    });
  }
  function close() { requestSequence.current += 1; setLoadId(null); setLoading(false); setDefinition(null); setDetail(null); setError(""); setMessage(""); setConflict(false); }
  function change(value: ScenarioDraftDefinition) { setDefinition(value); setMessage(""); }
  return { definition, detail, dirty, message, error, conflict, loading, loadId, save, archive, open, create, close, change, accept, busy: loading || save.isPending || archive.isPending };
}
