import { useDeferredValue, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { OfferingDetails } from "../../features/request-template-studio/offering-details";
import type { AdminServiceCatalogOffering } from "../../features/service-catalog/api";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/button";
import { PageShell, PageHeader, PageActions, ErrorState, LoadingState } from "../../components/ui-page/page-components";
import { useSession } from "../../features/auth/session-provider";
import { fetchScenarioCatalog, type ScenarioCatalog } from "../../features/request-template-studio/scenario-api";
import { ScenarioCatalogExplorer } from "../../features/request-template-studio/scenario-catalog";
import { ScenarioCategoryForm } from "../../features/request-template-studio/scenario-category-form";
import { ScenarioWizard } from "../../features/request-template-studio/scenario-wizard";
import { useScenarioEditor } from "../../features/request-template-studio/use-scenario-editor";
import { useScenarioContext } from "../../features/request-template-studio/use-scenario-context";
import { useScenarioDirtyGuard } from "../../features/request-template-studio/use-scenario-dirty-guard";
import { ScenarioActionBar } from "../../features/request-template-studio/scenario-action-bar";
import { catalogEntries } from "../../features/request-template-studio/offering-card";
import { ScenarioCreateDialog } from "../../features/request-template-studio/scenario-create-dialog";

export function AdminRequestTemplateStudioPage() {
  const { offeringCode } = useParams();
  const [params] = useSearchParams();
  return <StudioWorkspace key={[offeringCode ?? "catalog", params.get("service"), params.get("offering"), params.get("template")].join(":")} />;
}
type Selection = { kind: "offering"; offering: AdminServiceCatalogOffering } | { kind: "scenario"; id: string } | { kind: "new" };

function StudioWorkspace() {
  const { session } = useSession();
  const canEdit = session?.actor_role === "admin";
  const cache = useQueryClient();
  const { offeringCode } = useParams();
  const [params] = useSearchParams();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [offset, setOffset] = useState(0);
  const [category, setCategory] = useState<string | null>(() => params.get("service") ? `service:${params.get("service")}` : null);
  const [categoryEditor, setCategoryEditor] = useState<string | null>(null);
  const [categoryDirty, setCategoryDirty] = useState(false);
  const [inlineCategoryOpen, setInlineCategoryOpen] = useState(false);
  const [confirm, setConfirm] = useState<"leave" | "archive" | "switch" | null>(null);
  const [pending, setPending] = useState<Selection | null>(null);
  const [entryFocus, setEntryFocus] = useState<string | undefined>();
  const [catalogDirty, setCatalogDirty] = useState(false);
  const [explorerTab, setExplorerTab] = useState<"catalog" | "blocks">("blocks");
  const [selecting, setSelecting] = useState(false);
  const [selectionNotice, setSelectionNotice] = useState("");
  const [chooserData, setChooserData] = useState<ScenarioCatalog | null>(null);
  const [editorCatalog, setEditorCatalog] = useState<ScenarioCatalog | null>(null);
  const [newMap, setNewMap] = useState<{ offering?: AdminServiceCatalogOffering } | null>(null);
  const deferredQuery = useDeferredValue(query);
  const catalog = useQuery({ queryKey: ["scenario-catalog", offeringCode, deferredQuery, status, offset, category], queryFn: () => offeringCode ? fetchScenarioCatalog("", "all", 0, null, offeringCode) : fetchScenarioCatalog(deferredQuery, status, offset, category), placeholderData: previous => previous });
  const editor = useScenarioEditor(canEdit && !categoryDirty && !inlineCategoryOpen && !selecting && !confirm && !newMap, false);
  const contextNotice = useScenarioContext(catalog.data, editor, canEdit, createForOffering);
  useScenarioDirtyGuard(editor.dirty || categoryDirty || catalogDirty);
  const editing = !!editor.definition;
  const offering = catalog.data?.offerings.find(item => item.full_code === offeringCode);
  function createForOffering(item: AdminServiceCatalogOffering) {
    setNewMap({ offering: item });
  }
  async function select(selection: Selection) {
    setSelectionNotice(""); setChooserData(null);
    if (selection.kind === "new") { setNewMap({}); return; }
    if (selection.kind === "scenario") { await editor.open(selection.id); setExplorerTab("blocks"); return; }
    setSelecting(true);
    try {
      const data = await fetchScenarioCatalog("", "all", 0, null, selection.offering.full_code);
      const item = catalogEntries(data).find(card => card.offering.full_code === selection.offering.full_code)?.offering;
      if (!item) { setSelectionNotice("Услуга недоступна. Обновите каталог и выберите другой пункт."); return; }
      setEditorCatalog(data);
      const maps = data.scenarios.filter(map => map.offering_full_code === item.full_code && !map.archived);
      if (maps.length === 1) { await editor.open(maps[0].id); setExplorerTab("blocks"); }
      else if (maps.length > 1) { setChooserData(data); setExplorerTab("catalog"); setSelectionNotice("Для услуги есть несколько карт. Выберите нужную в левой панели."); }
      else if (canEdit && item.request_template_key && item.service_code) { createForOffering(item); setExplorerTab("blocks"); }
      else { setSelectionNotice(canEdit ? "Для этой услуги сначала нужен шаблон обработки. Откройте настройки услуги в каталоге." : "У услуги пока нет карты. Создание доступно администратору."); setExplorerTab("catalog"); }
    } catch { setSelectionNotice("Не удалось открыть услугу. Повторите выбор в каталоге."); }
    finally { setSelecting(false); }
  }
  function requestSelection(selection: Selection) {
    if (editor.busy || selecting || !!confirm || inlineCategoryOpen) return;
    if (selection.kind === "offering" && selection.offering.full_code === editor.definition?.offering_full_code) { setExplorerTab("blocks"); return; }
    if (selection.kind === "scenario" && selection.id === editor.detail?.scenario.id) { setExplorerTab("blocks"); return; }
    if (editor.dirty || categoryDirty) { setPending(selection); setConfirm("switch"); }
    else void select(selection);
  }
  const workbenchCatalog = catalog.data && editorCatalog ? { ...catalog.data, offerings: [...catalog.data.offerings, ...editorCatalog.offerings.filter(item => !catalog.data!.offerings.some(other => other.full_code === item.full_code))], services: [...catalog.data.services, ...editorCatalog.services.filter(item => !catalog.data!.services.some(other => other.code === item.code))], categories: [...catalog.data.categories, ...editorCatalog.categories.filter(item => !catalog.data!.categories.some(other => other.id === item.id))] } : catalog.data;
  function leave() { setEntryFocus(undefined); if (editor.dirty || categoryDirty) setConfirm("leave"); else editor.close(); }
  return <PageShell width="full" className="studio-workspace">
    <div className={editing ? "studio-workspace-heading bg-white/95" : "bg-white/95 pb-3"}>
      <PageHeader title={editing ? "Студия обращений" : "Каталог услуг"} description={editing ? undefined : offeringCode ? "Форма, сценарий и история одной услуги." : "Настраивайте услуги, которые видят сотрудники, и способы помощи для них."} actions={<ScenarioActionBar><PageActions>
        {editing ? <>{offeringCode && <Button variant="ghost" disabled={editor.busy || selecting || !!confirm || inlineCategoryOpen} onClick={leave}>Вернуться к услуге</Button>}{canEdit && !offeringCode && <Button variant="ghost" disabled={editor.busy || selecting || !!confirm || inlineCategoryOpen} onClick={() => requestSelection({ kind: "new" })}>Новая карта</Button>}{canEdit && !editor.detail?.scenario.archived && <Button disabled={editor.busy || selecting || !!confirm || inlineCategoryOpen || !editor.dirty || !editor.definition?.title.trim() || !editor.definition.offering_full_code} onClick={() => editor.save.mutate()}>Сохранить черновик</Button>}</> : offeringCode ? <Link className="inline-flex min-h-11 items-center px-4 text-sm font-semibold underline" to="/app/admin/request-template-studio">Вернуться в каталог</Link> : null}
      </PageActions></ScenarioActionBar>} />
    </div>
    {!canEdit && <p className="text-sm text-slate-500">Режим чтения: изменения доступны администратору.</p>}
    {contextNotice && <p role="status">{contextNotice}</p>}
    {editing && !editor.message && <p role="status" className="studio-save-status">{editor.save.isPending ? "Сохранение черновика…" : editor.conflict ? "Конфликт ревизий — правки остаются в редакторе" : editor.dirty ? "Изменения не сохранены" : editor.detail ? "Черновик сохранён" : "Выберите услугу или карту в каталоге слева — либо начните новую карту."}</p>}
    {selectionNotice && <p role="status">{selectionNotice}</p>}
    {(editor.loading || selecting) && <p role="status">Открытие карты…</p>}
    {editor.message && <p role="status" className="studio-save-status text-emerald-900">{editor.message}</p>}
    {editor.error && <div role="alert" className="space-y-2 rounded-md bg-amber-50 p-3"><p>{editor.error}</p>{editor.loadId && <Button variant="secondary" disabled={editor.busy || selecting || !!confirm} onClick={() => editor.open(editor.loadId!)}>Загрузить серверную версию</Button>}</div>}
    {catalog.isError && catalog.data && <div role="alert">Не удалось обновить каталог. Показана предыдущая версия; локальные настройки сохранены. <Button variant="ghost" onClick={()=>void catalog.refetch()}>Повторить обновление каталога</Button></div>}
    {catalog.isPending ? <LoadingState label="Загрузка Студии" /> : catalog.isError && !catalog.data ? <ErrorState title="Каталог недоступен" message="Не удалось получить сценарии. Проверьте соединение и повторите." onRetry={() => void catalog.refetch()} /> : catalog.data && workbenchCatalog && <>
      {categoryEditor ? <ScenarioCategoryForm key={categoryEditor} catalog={catalog.data} category={catalog.data.categories.find(item => item.id === categoryEditor)} onDirty={setCategoryDirty} onCancel={() => setCategoryEditor(null)} onDone={async () => { await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); setCategoryEditor(null); }} /> : editing && editor.definition ? <>
        <ScenarioWizard entryFocus={entryFocus} key={editor.definition.scenario_key} definition={editor.definition} detail={editor.detail} catalog={workbenchCatalog} disabled={!canEdit || editor.loading || selecting || !!confirm || editor.archive.isPending || !!editor.detail?.scenario.archived} simulationDisabled={editor.busy || selecting || !!editor.detail?.scenario.archived || !(canEdit || session?.actor_role === "auditor")} dirty={editor.dirty} onChange={editor.change} onAccept={editor.accept} onCatalog={leave} explorerTab={explorerTab} onExplorerTab={setExplorerTab} catalogPanel={{ data: chooserData ?? catalog.data, query, category, status, canEdit, busy: editor.busy || selecting || !!confirm || inlineCategoryOpen, selectedOffering: editor.definition.offering_full_code, onQuery: value => { setChooserData(null); setQuery(value); setOffset(0); }, onStatus: value => { setChooserData(null); setStatus(value); setOffset(0); }, onCategory: value => { setChooserData(null); setCategory(value); setOffset(0); }, onOffering: item => requestSelection({ kind: "offering", offering: item }), onScenario: item => requestSelection({ kind: "scenario", id: item.id }), onNew: () => requestSelection({ kind: "new" }), onNewCategory: () => setCategoryEditor("new"), onPage: setOffset, onBack: chooserData ? () => setChooserData(null) : undefined }} onCategoryDirty={setCategoryDirty} onCategoryOpen={setInlineCategoryOpen} onCategoryCreated={async () => { await cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }} />
        {canEdit && editor.detail && <div className="flex flex-wrap gap-2"><Button variant="ghost" disabled={editor.busy || selecting || !!confirm || editor.dirty || inlineCategoryOpen} onClick={() => editor.create(editor.definition!)}>Создать копию</Button>{!editor.detail.scenario.archived && <Button variant="ghost" disabled={editor.busy || selecting || !!confirm || editor.dirty || inlineCategoryOpen} onClick={() => setConfirm("archive")}>Архивировать сценарий</Button>}</div>}
      </> : <ScenarioCatalogExplorer data={chooserData ?? catalog.data} query={query} status={status} category={category} canEdit={canEdit} onQuery={value => { setQuery(value); setOffset(0); }} onStatus={value => { setStatus(value); setOffset(0); }} onCategory={value => { setCategory(value); setOffset(0); }} initialOffering={offeringCode} onDirty={setCatalogDirty} onNewMap={() => setNewMap({})} onOpen={(item,blockId) => { setEntryFocus(blockId); void editor.open(item.id); }} onCreateForOffering={createForOffering} onEditCategory={setCategoryEditor} onPage={setOffset} />}
    </>}
    {newMap && workbenchCatalog && <ScenarioCreateDialog catalog={workbenchCatalog} offering={newMap.offering} onClose={() => setNewMap(null)} onCreate={draft => { editor.create(draft, false); setExplorerTab("blocks"); setNewMap(null); }} onOfferingCreated={saved => { setEditorCatalog(previous => ({ ...(previous ?? workbenchCatalog), offerings: [...(previous ?? workbenchCatalog).offerings.filter(item => item.full_code !== saved.full_code), saved] })); void cache.invalidateQueries({ queryKey: ["scenario-catalog"] }); }} />}
    {confirm && <div role="alert" className="rounded-xl border border-amber-300 p-4"><p>{confirm === "leave" ? "Уйти без сохранения локальных изменений?" : confirm === "switch" ? "Переключить карту без сохранения локальных изменений?" : "Архивировать сценарий? Новые пользовательские сеансы будут недоступны."}</p><div className="mt-3 flex flex-wrap gap-2"><Button disabled={editor.busy || selecting} onClick={() => { if (confirm === "leave") editor.close(); else if (confirm === "switch" && pending) { editor.close(); void select(pending); } else editor.archive.mutate(); setPending(null); setConfirm(null); }}>{confirm === "leave" ? "Уйти без сохранения" : confirm === "switch" ? "Переключить без сохранения" : "Подтвердить архивирование"}</Button><Button variant="ghost" onClick={() => { setPending(null); setConfirm(null); }}>Отмена</Button></div></div>}
  </PageShell>;
}
