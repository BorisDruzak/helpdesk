import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Save, Trash2, X } from "lucide-react";

import { Button } from "../../components/ui/button";
import {
  addKnowledgeItemBinding,
  deleteKnowledgeItemBinding,
  fetchKnowledgeItemBindings,
  fetchKnowledgeServiceCatalogOptions,
  updateKnowledgeItemBinding,
  type KnowledgeItem,
  type KnowledgeItemBinding,
  type KnowledgeItemBindingInput,
  type KnowledgeServiceCatalogOption,
} from "./api";
import { fieldClass } from "./authoring/knowledge-studio-model";

const surfaceOptions = [
  {
    value: "requester_pre_submit",
    label: "Форма обращения до отправки",
    description: "Статья может появиться как подсказка до создания заявки.",
  },
  {
    value: "requester_after_submit",
    label: "Портал заявителя после отправки",
    description: "Статья доступна в уже созданном обращении заявителя.",
  },
  {
    value: "support_ticket_workspace",
    label: "Карточка тикета поддержки",
    description: "Поддержка увидит статью в контексте выбранного тикета.",
  },
  {
    value: "support_command_center",
    label: "Командный центр поддержки",
    description: "Статья может попасть в рабочие подборки поддержки.",
  },
  {
    value: "agent",
    label: "Агент",
    description: "Локальный агент может использовать статью как requester-safe подсказку.",
  },
  {
    value: "ai_rag",
    label: "AI/RAG",
    description: "Статья может стать источником AI-ответа, если разрешена политикой RAG.",
  },
] as const;

const defaultSurfaces = ["requester_pre_submit", "support_ticket_workspace"];

type BindingDraft = {
  offering_code: string;
  request_template_key: string;
  service_code: string;
  surfaces: string[];
  ticket_type: string;
};

function emptyDraft(): BindingDraft {
  return {
    offering_code: "",
    request_template_key: "",
    service_code: "",
    surfaces: [...defaultSurfaces],
    ticket_type: "",
  };
}

function emptyToNull(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function surfacesFrom(binding: KnowledgeItemBinding): string[] {
  const raw = binding.metadata?.surfaces;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw.map((item) => String(item)).filter(Boolean);
}

function draftFrom(binding: KnowledgeItemBinding): BindingDraft {
  const surfaces = surfacesFrom(binding);
  return {
    offering_code: binding.offering_code ?? "",
    request_template_key: binding.request_template_key ?? "",
    service_code: binding.service_code ?? "",
    surfaces: surfaces.length ? surfaces : [...defaultSurfaces],
    ticket_type: binding.ticket_type ?? "",
  };
}

function payloadFrom(draft: BindingDraft): KnowledgeItemBindingInput {
  return {
    service_code: emptyToNull(draft.service_code),
    offering_code: emptyToNull(draft.offering_code),
    request_template_key: emptyToNull(draft.request_template_key),
    ticket_type: emptyToNull(draft.ticket_type),
    weight: 1,
    metadata: { surfaces: draft.surfaces },
  };
}

function bindingTitle(binding: KnowledgeItemBinding, options: KnowledgeServiceCatalogOption[]) {
  const offeringLabel = options.find((option) => option.type === "offering" && option.value === binding.offering_code)?.label;
  const serviceLabel = options.find((option) => option.type === "service" && option.value === binding.service_code)?.label;
  if (offeringLabel) {
    return offeringLabel;
  }
  if (serviceLabel) {
    return serviceLabel;
  }
  return [binding.service_code, binding.offering_code, binding.request_template_key].filter(Boolean).join(" / ") || "Контекст обращения";
}

function surfaceLabels(values: string[]) {
  return surfaceOptions.filter((option) => values.includes(option.value)).map((option) => option.label);
}

type ArticleHelpDeskBindingPanelProps = {
  item: KnowledgeItem | null;
  visibility: string;
};

export function ArticleHelpDeskBindingPanel({ item, visibility }: ArticleHelpDeskBindingPanelProps) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<BindingDraft>(() => emptyDraft());
  const [editingBindingId, setEditingBindingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const bindingsQuery = useQuery({
    queryKey: ["knowledge-item-bindings", item?.item_id],
    queryFn: () => fetchKnowledgeItemBindings(item?.item_id ?? ""),
    enabled: Boolean(item?.item_id),
  });
  const catalogQuery = useQuery({
    queryKey: ["knowledge-service-catalog-options"],
    queryFn: fetchKnowledgeServiceCatalogOptions,
  });

  const catalogOptions = catalogQuery.data ?? [];
  const serviceOptions = useMemo(() => catalogOptions.filter((option) => option.type === "service"), [catalogOptions]);
  const offeringOptions = useMemo(
    () =>
      catalogOptions.filter((option) => option.type === "offering" && (!draft.service_code || option.service_code === draft.service_code)),
    [catalogOptions, draft.service_code],
  );
  const selectedSurfaceLabels = surfaceLabels(draft.surfaces);
  const savedBindings = bindingsQuery.data ?? [];
  const canSave = Boolean(item?.item_id)
    && Boolean(draft.service_code || draft.offering_code || draft.request_template_key)
    && draft.surfaces.length > 0;

  useEffect(() => {
    setDraft(emptyDraft());
    setEditingBindingId(null);
    setMessage("");
  }, [item?.item_id]);

  const saveMutation = useMutation({
    mutationFn: () => {
      const itemId = item?.item_id ?? "";
      const payload = payloadFrom(draft);
      if (editingBindingId) {
        return updateKnowledgeItemBinding(itemId, editingBindingId, payload);
      }
      return addKnowledgeItemBinding(itemId, payload);
    },
    onSuccess: () => {
      setMessage(editingBindingId ? "Связь с обращениями обновлена." : "Связь с обращениями сохранена.");
      setEditingBindingId(null);
      setDraft(emptyDraft());
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-bindings", item?.item_id] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (bindingId: string) => deleteKnowledgeItemBinding(item?.item_id ?? "", bindingId),
    onSuccess: () => {
      setMessage("Связь с обращениями удалена.");
      setEditingBindingId(null);
      setDraft(emptyDraft());
      queryClient.invalidateQueries({ queryKey: ["knowledge-item-bindings", item?.item_id] });
    },
  });

  function changeService(serviceCode: string) {
    setMessage("");
    setDraft((current) => ({
      ...current,
      offering_code: "",
      request_template_key: current.service_code === serviceCode ? current.request_template_key : "",
      service_code: serviceCode,
    }));
  }

  function changeOffering(offeringCode: string) {
    setMessage("");
    const selected = offeringOptions.find((option) => option.value === offeringCode);
    setDraft((current) => ({
      ...current,
      offering_code: offeringCode,
      request_template_key: selected?.request_template_key ?? current.request_template_key,
      service_code: selected?.service_code ?? current.service_code,
    }));
  }

  function toggleSurface(surface: string) {
    setMessage("");
    setDraft((current) => {
      const next = current.surfaces.includes(surface)
        ? current.surfaces.filter((item) => item !== surface)
        : [...current.surfaces, surface];
      return { ...current, surfaces: next };
    });
  }

  function startEdit(binding: KnowledgeItemBinding) {
    if (!binding.binding_id) {
      return;
    }
    setMessage("");
    setEditingBindingId(binding.binding_id);
    setDraft(draftFrom(binding));
  }

  function cancelEdit() {
    setMessage("");
    setEditingBindingId(null);
    setDraft(emptyDraft());
  }

  function deleteBinding(binding: KnowledgeItemBinding) {
    if (!binding.binding_id) {
      return;
    }
    if (!window.confirm("Удалить связь статьи с этим контекстом обращения?")) {
      return;
    }
    setMessage("");
    deleteMutation.mutate(binding.binding_id);
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-950">Связь с обращениями</h3>
          <p className="mt-1 text-sm font-semibold text-slate-800">Сервис, услуга, шаблон и поверхности показа</p>
          <p className="mt-1 text-sm text-slate-500">
            Привязка определяет, где статья будет предложена: до отправки заявки, в карточке тикета, в агенте или в AI/RAG. Эти поверхности уже используются сервером как контракт eligibility.
          </p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold text-slate-600">
          {visibility === "support_internal" ? "Внутренняя подсказка поддержки" : "Requester-safe при выбранной аудитории"}
        </span>
      </div>

      <div className="mt-4 grid gap-3">
        <label className="text-sm font-medium">
          Сервис
          <select className={fieldClass} disabled={!item} value={draft.service_code} onChange={(event) => changeService(event.currentTarget.value)}>
            <option value="">Выберите сервис</option>
            {serviceOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Услуга
          <select className={fieldClass} disabled={!item || !offeringOptions.length} value={draft.offering_code} onChange={(event) => changeOffering(event.currentTarget.value)}>
            <option value="">Можно оставить пустой</option>
            {offeringOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm font-medium">
          Шаблон обращения
          <input
            className={fieldClass}
            disabled={!item}
            onChange={(event) => setDraft((current) => ({ ...current, request_template_key: event.currentTarget.value }))}
            placeholder="Например: network"
            value={draft.request_template_key}
          />
        </label>
      </div>

      <div className="mt-3 grid gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">Где статья будет предложена</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Выберите хотя бы одну поверхность. Для AI-ответов нужна отдельная поверхность AI/RAG и включённая политика RAG у раздела или статьи.
          </p>
          <div className="mt-2 grid gap-2">
            {surfaceOptions.map((option) => (
              <label key={option.value} className="flex gap-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <input checked={draft.surfaces.includes(option.value)} disabled={!item} onChange={() => toggleSurface(option.value)} type="checkbox" />
                <span>
                  <span className="block font-semibold text-slate-900">{option.label}</span>
                  <span className="mt-1 block text-xs leading-5 text-slate-500">{option.description}</span>
                </span>
              </label>
            ))}
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
          <p className="font-semibold text-slate-950">Предпросмотр</p>
          {selectedSurfaceLabels.length ? (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
              {selectedSurfaceLabels.map((label) => (
                <li key={label}>{label}</li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-red-700">Выберите хотя бы один сценарий показа.</p>
          )}
          <label className="mt-3 block text-sm font-medium">
            Тип тикета
            <input
              className={fieldClass}
              disabled={!item}
              onChange={(event) => setDraft((current) => ({ ...current, ticket_type: event.currentTarget.value }))}
              placeholder="incident, request"
              value={draft.ticket_type}
            />
          </label>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button
          disabled={!canSave || saveMutation.isPending}
          leadingIcon={<Save className="h-4 w-4" />}
          onClick={() => saveMutation.mutate()}
          type="button"
        >
          {editingBindingId ? "Обновить связь" : "Сохранить связь"}
        </Button>
        {editingBindingId ? (
          <Button leadingIcon={<X className="h-4 w-4" />} onClick={cancelEdit} type="button" variant="outline">
            Отмена
          </Button>
        ) : null}
        {saveMutation.isError ? <p className="text-sm text-red-700">{String(saveMutation.error?.message ?? "Не удалось сохранить связь")}</p> : null}
        {deleteMutation.isError ? <p className="text-sm text-red-700">{String(deleteMutation.error?.message ?? "Не удалось удалить связь")}</p> : null}
        {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
      </div>

      <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
        <p className="text-sm font-semibold text-slate-950">Сохранённые связи</p>
        {bindingsQuery.isLoading ? <p className="mt-2 text-sm text-slate-500">Загружаем связи...</p> : null}
        {savedBindings.length ? (
          <div className="mt-2 space-y-2">
            {savedBindings.map((binding, index) => {
              const labels = surfaceLabels(surfacesFrom(binding));
              return (
                <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm" key={binding.binding_id ?? `${binding.item_id}-${index}`}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold text-slate-900">{bindingTitle(binding, catalogOptions)}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {[binding.service_code, binding.offering_code, binding.request_template_key].filter(Boolean).join(" / ") || "Контекст не задан"}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        disabled={!binding.binding_id || saveMutation.isPending || deleteMutation.isPending}
                        leadingIcon={<Pencil className="h-4 w-4" />}
                        onClick={() => startEdit(binding)}
                        size="sm"
                        title="Изменить связь"
                        type="button"
                        variant="outline"
                      >
                        Изменить
                      </Button>
                      <Button
                        disabled={!binding.binding_id || deleteMutation.isPending}
                        leadingIcon={<Trash2 className="h-4 w-4" />}
                        onClick={() => deleteBinding(binding)}
                        size="sm"
                        title="Удалить связь"
                        type="button"
                        variant="ghost"
                      >
                        Удалить
                      </Button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    {labels.length ? labels.join(", ") : "Не ограничено: старая связь работает во всех сценариях."}
                  </p>
                </div>
              );
            })}
          </div>
        ) : !bindingsQuery.isLoading ? (
          <p className="mt-2 text-sm text-slate-500">Пока нет связей с сервисом, услугой или шаблоном обращения.</p>
        ) : null}
      </div>
    </section>
  );
}
