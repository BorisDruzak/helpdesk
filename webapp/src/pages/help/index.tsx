import { useMutation, useQuery } from "@tanstack/react-query";
import { Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Select } from "../../components/ui/select";
import {
  createPublicTicket,
  fetchPublicFormPack,
  fetchServiceCatalogCurrent,
  previewServiceCatalogRequest,
  recordKnowledgeFeedback,
  suggestKnowledge,
} from "../../features/requester/api";
import type {
  PublicTicketCreatePayload,
  PublicTicketCreateResult,
  KnowledgeAttempt,
  KnowledgeSuggestionItem,
  RequestFormDefinition,
  RequestFormField,
  ServiceCatalogPreviewPayload,
} from "../../features/requester/types";

type FieldValues = Record<string, string | boolean>;

function tokenStorageKey(ticketId: string): string {
  return `public_ticket_token:${ticketId}`;
}

function isFieldVisible(field: RequestFormField, values: FieldValues): boolean {
  const rule = field.visible_when;
  if (!rule?.field) {
    return true;
  }
  const currentValue = values[rule.field];
  if (Object.prototype.hasOwnProperty.call(rule, "equals")) {
    return String(currentValue ?? "").trim() === String(rule.equals ?? "").trim();
  }
  if (Array.isArray(rule.in)) {
    return rule.in.map((item) => String(item ?? "").trim()).includes(String(currentValue ?? "").trim());
  }
  return true;
}

function buildDefaultFieldValues(form: RequestFormDefinition | null): FieldValues {
  const nextValues: FieldValues = {};
  for (const field of form?.fields ?? []) {
    nextValues[field.key] = field.type === "checkbox" ? false : "";
  }
  return nextValues;
}

function collectVisiblePayload(form: RequestFormDefinition | null, values: FieldValues): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const field of form?.fields ?? []) {
    if (isFieldVisible(field, values)) {
      payload[field.key] = values[field.key] ?? (field.type === "checkbox" ? false : "");
    }
  }
  return payload;
}

function missingRequiredFields(form: RequestFormDefinition | null, values: FieldValues): string[] {
  return (form?.fields ?? [])
    .filter((field) => field.required && isFieldVisible(field, values))
    .filter((field) => {
      const value = values[field.key];
      return field.type === "checkbox" ? value !== true : !String(value ?? "").trim();
    })
    .map((field) => field.label || field.key);
}

function FieldControl({
  field,
  onChange,
  value,
}: {
  field: RequestFormField;
  onChange: (value: string | boolean) => void;
  value: string | boolean;
}) {
  const label = `${field.label || field.key}${field.required ? " *" : ""}`;

  if (field.type === "textarea") {
    return (
      <label className="grid gap-2 text-sm font-medium text-slate-700">
        <span>{label}</span>
        <textarea
          className="field-base min-h-28 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400"
          onChange={(event) => onChange(event.currentTarget.value)}
          placeholder={field.placeholder ?? ""}
          value={String(value ?? "")}
        />
      </label>
    );
  }

  if (field.type === "select" || field.type === "radio") {
    return (
      <label className="grid gap-2 text-sm font-medium text-slate-700">
        <span>{label}</span>
        <Select onChange={(event) => onChange(event.currentTarget.value)} value={String(value ?? "")}>
          <option value="">Выберите...</option>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label || option.value}
            </option>
          ))}
        </Select>
      </label>
    );
  }

  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-3 rounded-[1rem] border border-border bg-white px-4 py-3 text-sm font-medium text-slate-700">
        <input checked={value === true} onChange={(event) => onChange(event.currentTarget.checked)} type="checkbox" />
        <span>{label}</span>
      </label>
    );
  }

  return (
    <label className="grid gap-2 text-sm font-medium text-slate-700">
      <span>{label}</span>
      <Input
        onChange={(event) => onChange(event.currentTarget.value)}
        placeholder={field.placeholder ?? ""}
        type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
        value={String(value ?? "")}
      />
    </label>
  );
}

export function HelpPage() {
  const [selectedServiceCode, setSelectedServiceCode] = useState("");
  const [selectedOfferingFullCode, setSelectedOfferingFullCode] = useState("");
  const [selectedFormKey, setSelectedFormKey] = useState("");
  const [fieldValues, setFieldValues] = useState<FieldValues>({});
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [building, setBuilding] = useState("");
  const [room, setRoom] = useState("");
  const [urgency, setUrgency] = useState(false);
  const [importance, setImportance] = useState(false);
  const [feedback, setFeedback] = useState<{ tone: "error" | "success"; text: string } | null>(null);
  const [createdTicket, setCreatedTicket] = useState<PublicTicketCreateResult | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [knowledgeAttempts, setKnowledgeAttempts] = useState<KnowledgeAttempt[]>([]);
  const [openedKnowledge, setOpenedKnowledge] = useState<KnowledgeSuggestionItem | null>(null);

  const formsQuery = useQuery({
    queryKey: ["requester-form-pack"],
    queryFn: fetchPublicFormPack,
    retry: false,
  });

  const catalogQuery = useQuery({
    queryKey: ["service-catalog-current"],
    queryFn: fetchServiceCatalogCurrent,
    retry: false,
  });

  const forms = formsQuery.data?.forms ?? [];
  const services = catalogQuery.data?.services ?? [];
  const selectedService = useMemo(
    () => services.find((service) => service.service_code === selectedServiceCode) ?? services[0] ?? null,
    [selectedServiceCode, services],
  );
  const selectedOffering = useMemo(
    () =>
      selectedService?.offerings.find((offering) => offering.full_code === selectedOfferingFullCode) ??
      selectedService?.offerings[0] ??
      null,
    [selectedOfferingFullCode, selectedService],
  );
  const selectedForm = useMemo(
    () => forms.find((form) => form.key === selectedFormKey) ?? forms[0] ?? null,
    [forms, selectedFormKey],
  );
  const visibleFields = useMemo(
    () => (selectedForm?.fields ?? []).filter((field) => isFieldVisible(field, fieldValues)),
    [fieldValues, selectedForm],
  );
  const visiblePayload = useMemo(() => collectVisiblePayload(selectedForm, fieldValues), [fieldValues, selectedForm]);
  const currentPreviewKey = useMemo(
    () =>
      JSON.stringify({
        service: selectedService?.service_code,
        offering: selectedOffering?.full_code,
        form: selectedForm?.key,
        payload: visiblePayload,
        description,
        displayName,
        fullName,
        phone,
        building,
        room,
        urgency,
        importance,
      }),
    [
      building,
      description,
      displayName,
      visiblePayload,
      fullName,
      importance,
      phone,
      room,
      selectedForm,
      selectedOffering?.full_code,
      selectedService?.service_code,
      urgency,
    ],
  );

  const knowledgeQuery = useQuery({
    queryKey: [
      "knowledge-suggest",
      selectedService?.service_code,
      selectedOffering?.full_code,
      selectedForm?.key,
      description.slice(0, 240),
      visiblePayload,
    ],
    queryFn: () =>
      suggestKnowledge({
        service_code: selectedService?.service_code,
        offering_code: selectedOffering?.full_code,
        request_template_key: selectedOffering?.request_template_key ?? selectedForm?.key,
        query: description || selectedOffering?.title || selectedService?.title || "",
        form_payload: visiblePayload,
        surface: "requester_portal",
      }),
    enabled: Boolean(selectedOffering),
    retry: false,
  });

  function appendKnowledgeAttempt(item: KnowledgeSuggestionItem, result: KnowledgeAttempt["result"]) {
    const attempt: KnowledgeAttempt = {
      item_id: item.item_id,
      version_id: item.version_id ?? null,
      result,
      surface: "requester_portal",
      timestamp: new Date().toISOString(),
    };
    setKnowledgeAttempts((current) => [...current.filter((entry) => entry.item_id !== item.item_id || entry.result !== result), attempt]);
    return attempt;
  }

  function recordKnowledgeAttempt(item: KnowledgeSuggestionItem, result: KnowledgeAttempt["result"]) {
    appendKnowledgeAttempt(item, result);
    void recordKnowledgeFeedback({
      item_id: item.item_id,
      version_id: item.version_id,
      event_type: result === "deflected" ? "deflected" : result === "not_helpful" ? "not_helpful" : result === "helpful" ? "helpful" : "viewed",
      service_code: selectedService?.service_code,
      offering_code: selectedOffering?.full_code,
      request_template_key: selectedOffering?.request_template_key ?? selectedForm?.key,
      surface: "requester_portal",
    });
  }

  function buildCreatePayload(): PublicTicketCreatePayload {
    if (!displayName.trim()) {
      throw new Error("Укажите, как к вам обращаться.");
    }
    if (!description.trim()) {
      throw new Error("Опишите проблему.");
    }
    const missing = missingRequiredFields(selectedForm, fieldValues);
    if (missing.length) {
      throw new Error(`Заполните обязательные поля: ${missing.join(", ")}`);
    }
    const formPayload = visiblePayload;
    return {
      title: selectedForm ? `Заявка: ${selectedForm.title || selectedForm.key}` : "Заявка с веб-страницы",
      description: description.trim(),
      user_display_name: displayName.trim(),
      requester_profile: {
        full_name: fullName.trim() || displayName.trim(),
        building: building.trim(),
        room: room.trim(),
        phone: phone.trim(),
      },
      urgency,
      importance,
      urgency_reason: urgency ? "requester_marked_urgent" : "requester_did_not_mark_urgent",
      importance_reason: importance ? "requester_marked_important" : "requester_did_not_mark_important",
      ...(selectedForm && formsQuery.data
        ? {
            form_key: selectedForm.key,
            form_pack_key: formsQuery.data.pack_key,
            form_pack_version: formsQuery.data.version,
            form_payload: formPayload,
            ticket_type: selectedForm.request_kind || selectedForm.key,
            request_template_key: selectedOffering?.request_template_key ?? selectedForm.key,
            service_code: selectedService?.service_code,
            offering_code: selectedOffering?.offering_code,
            offering_full_code: selectedOffering?.full_code,
            knowledge_attempts: knowledgeAttempts,
          }
        : {}),
    };
  }

  function buildPreviewPayload(): ServiceCatalogPreviewPayload {
    const createPayload = buildCreatePayload();
    return {
      service_code: createPayload.service_code,
      offering_code: createPayload.offering_code,
      offering_full_code: createPayload.offering_full_code,
      request_template_key: createPayload.request_template_key,
      form_key: createPayload.form_key,
      form_pack_key: createPayload.form_pack_key,
      form_pack_version: createPayload.form_pack_version,
      form_payload: createPayload.form_payload,
      description: createPayload.description,
      requester_context: {
        requester_profile: createPayload.requester_profile,
      },
    };
  }

  useEffect(() => {
    if (!selectedServiceCode && services[0]) {
      setSelectedServiceCode(services[0].service_code);
    }
  }, [selectedServiceCode, services]);

  useEffect(() => {
    if (selectedService?.offerings[0] && !selectedOfferingFullCode) {
      setSelectedOfferingFullCode(selectedService.offerings[0].full_code);
    }
  }, [selectedOfferingFullCode, selectedService]);

  useEffect(() => {
    if (selectedOffering?.request_template_key) {
      setSelectedFormKey(selectedOffering.request_template_key);
    }
  }, [selectedOffering?.request_template_key]);

  useEffect(() => {
    if (!selectedFormKey && forms[0]) {
      setSelectedFormKey(forms[0].key);
    }
  }, [forms, selectedFormKey]);

  useEffect(() => {
    setFieldValues(buildDefaultFieldValues(selectedForm));
  }, [selectedForm?.key]);

  const previewMutation = useMutation({
    mutationFn: () => previewServiceCatalogRequest(buildPreviewPayload()),
    onSuccess: (result) => {
      setPreviewKey(currentPreviewKey);
      const blockers = result.blockers ?? [];
      const warnings = result.warnings ?? [];
      setFeedback({
        tone: blockers.length ? "error" : "success",
        text: blockers.length
          ? blockers.join(" ")
          : warnings.length
            ? `Preview рассчитан. Предупреждения: ${warnings.join(" ")}`
            : "Preview рассчитан. Можно отправлять заявку.",
      });
    },
    onError: (error) => {
      setPreviewKey("");
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось построить безопасный preview обращения.",
      });
    },
  });

  const previewIsFresh =
    Boolean(selectedOffering) &&
    previewKey === currentPreviewKey &&
    Boolean(previewMutation.data?.ok) &&
    !(previewMutation.data?.blockers ?? []).length;

  const createMutation = useMutation({
    mutationFn: () => {
      if (selectedOffering && !previewIsFresh) {
        throw new Error("Сначала выполните безопасный preview заявки.");
      }
      return createPublicTicket(buildCreatePayload());
    },
    onSuccess: (result) => {
      const ticketId = result.ticket.ticket_id;
      if (ticketId && result.public_token) {
        sessionStorage.setItem(tokenStorageKey(ticketId), result.public_token);
      }
      setCreatedTicket(result);
      setPreviewKey("");
      setFeedback({ tone: "success", text: "Заявка создана." });
    },
    onError: (error) => {
      setFeedback({
        tone: "error",
        text: error instanceof Error ? error.message : "Не удалось создать заявку.",
      });
    },
  });

  const ticketId = createdTicket?.ticket.ticket_id;
  const accessCode = createdTicket?.public_access_code ?? "";

  return (
    <main className="min-h-screen bg-app px-4 py-6 md:px-8">
      <section className="mx-auto grid max-w-6xl gap-5 lg:grid-cols-[minmax(0,1.4fr)_360px]">
        <Card>
          <CardHeader>
            <CardTitle>Создать заявку</CardTitle>
            <CardDescription>
              Опишите проблему, и заявка сразу попадет в очередь поддержки с нужными полями для маршрутизации.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                createMutation.mutate();
              }}
            >
              <label className="grid gap-2 text-sm font-medium text-slate-700">
                <span>Как к вам обращаться</span>
                <Input onChange={(event) => setDisplayName(event.currentTarget.value)} value={displayName} />
              </label>

              <div className="grid gap-3 md:grid-cols-2">
                <label className="grid gap-2 text-sm font-medium text-slate-700">
                  <span>ФИО</span>
                  <Input onChange={(event) => setFullName(event.currentTarget.value)} value={fullName} />
                </label>
                <label className="grid gap-2 text-sm font-medium text-slate-700">
                  <span>Телефон</span>
                  <Input onChange={(event) => setPhone(event.currentTarget.value)} value={phone} />
                </label>
                <label className="grid gap-2 text-sm font-medium text-slate-700">
                  <span>Корпус</span>
                  <Input onChange={(event) => setBuilding(event.currentTarget.value)} value={building} />
                </label>
                <label className="grid gap-2 text-sm font-medium text-slate-700">
                  <span>Кабинет</span>
                  <Input onChange={(event) => setRoom(event.currentTarget.value)} value={room} />
                </label>
              </div>

              <label className="grid gap-2 text-sm font-medium text-slate-700">
                <span>Описание проблемы</span>
                <textarea
                  className="field-base min-h-32 px-4 py-3 text-sm text-slate-900 placeholder:text-slate-400"
                  onChange={(event) => setDescription(event.currentTarget.value)}
                  value={description}
                />
              </label>

              {formsQuery.isLoading ? (
                <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500">
                  Загружаем каталог форм...
                </div>
              ) : null}

              {catalogQuery.isLoading ? (
                <div className="rounded-[1rem] border border-dashed border-border bg-surface-subtle px-4 py-4 text-sm text-slate-500">
                  Загружаем каталог услуг...
                </div>
              ) : null}

              {services.length ? (
                <div className="grid gap-3">
                  <label className="grid gap-2 text-sm font-medium text-slate-700">
                    <span>Услуга</span>
                    <Select
                      onChange={(event) => {
                        const nextCode = event.currentTarget.value;
                        setSelectedServiceCode(nextCode);
                        const nextService = services.find((service) => service.service_code === nextCode);
                        setSelectedOfferingFullCode(nextService?.offerings[0]?.full_code ?? "");
                      }}
                      value={selectedService?.service_code ?? ""}
                    >
                      {services.map((service) => (
                        <option key={service.service_code} value={service.service_code}>
                          {service.title || service.service_code}
                        </option>
                      ))}
                    </Select>
                  </label>
                  {selectedService?.offerings.length ? (
                    <label className="grid gap-2 text-sm font-medium text-slate-700">
                      <span>Тип обращения</span>
                      <Select
                        onChange={(event) => setSelectedOfferingFullCode(event.currentTarget.value)}
                        value={selectedOffering?.full_code ?? ""}
                      >
                        {selectedService.offerings.map((offering) => (
                          <option key={offering.full_code} value={offering.full_code}>
                            {offering.title || offering.offering_code}
                          </option>
                        ))}
                      </Select>
                    </label>
                  ) : null}
                  {selectedOffering ? (
                    <div className="rounded-[1rem] border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-slate-700">
                      <p className="font-semibold text-slate-950">{selectedOffering.title}</p>
                      {selectedOffering.description ? <p className="mt-1">{selectedOffering.description}</p> : null}
                      <p className="mt-2 text-xs text-slate-600">
                        {[
                          selectedOffering.expected_response ? `Ответ: ${selectedOffering.expected_response}` : null,
                          selectedOffering.expected_resolution ? `Решение: ${selectedOffering.expected_resolution}` : null,
                          selectedOffering.approval_required ? "Потребуется согласование" : null,
                          selectedOffering.diagnostic_consent_required ? "Потребуется согласие на диагностику" : null,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "Маршрут и сроки будут рассчитаны безопасным предпросмотром процесса."}
                      </p>
                    </div>
                  ) : null}
                  {selectedOffering ? (
                    <div className="rounded-[1rem] border border-border bg-white px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-slate-950">Возможно, поможет</p>
                          <p className="mt-1 text-xs text-slate-500">
                            Инструкции подобраны по выбранной услуге и типу обращения. Можно продолжить создание заявки в любой момент.
                          </p>
                        </div>
                        {knowledgeQuery.isFetching ? <span className="text-xs text-slate-500">Ищем...</span> : null}
                      </div>
                      {knowledgeQuery.isError ? (
                        <p className="mt-3 text-xs text-amber-700">Инструкции временно недоступны, заявка создается обычным способом.</p>
                      ) : null}
                      {(knowledgeQuery.data?.suggestions ?? []).length ? (
                        <div className="mt-3 grid gap-2">
                          {(knowledgeQuery.data?.suggestions ?? []).slice(0, 3).map((item) => (
                            <div className="rounded-xl border border-slate-200 bg-surface-subtle px-3 py-2" key={item.item_id}>
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-sm font-semibold text-slate-950">{item.title}</p>
                                  {item.summary ? <p className="mt-1 text-xs text-slate-600">{item.summary}</p> : null}
                                  {openedKnowledge?.item_id === item.item_id && item.snippet ? (
                                    <p className="mt-2 rounded-lg bg-white px-3 py-2 text-xs text-slate-700">{item.snippet}</p>
                                  ) : null}
                                </div>
                                <Button
                                  onClick={() => {
                                    setOpenedKnowledge((current) => (current?.item_id === item.item_id ? null : item));
                                    recordKnowledgeAttempt(item, "viewed");
                                  }}
                                  size="sm"
                                  type="button"
                                  variant="secondary"
                                >
                                  {openedKnowledge?.item_id === item.item_id ? "Скрыть" : "Открыть"}
                                </Button>
                              </div>
                              <div className="mt-2 flex flex-wrap gap-2">
                                <Button
                                  onClick={() => {
                                    recordKnowledgeAttempt(item, "deflected");
                                    setFeedback({ tone: "success", text: "Отмечено: инструкция помогла, заявка не создавалась." });
                                  }}
                                  size="sm"
                                  type="button"
                                  variant="secondary"
                                >
                                  Помогло
                                </Button>
                                <Button
                                  onClick={() => recordKnowledgeAttempt(item, "not_helpful")}
                                  size="sm"
                                  type="button"
                                  variant="secondary"
                                >
                                  Не помогло
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : !knowledgeQuery.isFetching ? (
                        <p className="mt-3 text-xs text-slate-500">Подходящих опубликованных инструкций пока нет.</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}

              {forms.length ? (
                <>
                  <label className="grid gap-2 text-sm font-medium text-slate-700">
                    <span>{services.length ? "Форма обращения" : "Тип обращения"}</span>
                    <Select
                      onChange={(event) => setSelectedFormKey(event.currentTarget.value)}
                      value={selectedForm?.key ?? ""}
                    >
                      {forms.map((form) => (
                        <option key={form.key} value={form.key}>
                          {form.title || form.key}
                        </option>
                      ))}
                    </Select>
                  </label>

                  <div className="grid gap-3">
                    {visibleFields.map((field) => (
                      <FieldControl
                        field={field}
                        key={field.key}
                        onChange={(value) => {
                          setFieldValues((current) => ({ ...current, [field.key]: value }));
                        }}
                        value={fieldValues[field.key] ?? (field.type === "checkbox" ? false : "")}
                      />
                    ))}
                  </div>
                </>
              ) : null}

              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex items-center gap-3 rounded-[1rem] border border-border bg-white px-4 py-3 text-sm font-medium text-slate-700">
                  <input checked={urgency} onChange={(event) => setUrgency(event.currentTarget.checked)} type="checkbox" />
                  <span>Срочно</span>
                </label>
                <label className="flex items-center gap-3 rounded-[1rem] border border-border bg-white px-4 py-3 text-sm font-medium text-slate-700">
                  <input
                    checked={importance}
                    onChange={(event) => setImportance(event.currentTarget.checked)}
                    type="checkbox"
                  />
                  <span>Влияет на работу отдела</span>
                </label>
              </div>

              {feedback ? (
                <div
                  className={
                    feedback.tone === "error"
                      ? "rounded-[1rem] border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700"
                      : "rounded-[1rem] border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
                  }
                >
                  {feedback.text}
                </div>
              ) : null}

              <div className="grid gap-3 md:grid-cols-2">
                <Button
                  disabled={!selectedOffering || previewMutation.isPending || createMutation.isPending}
                  onClick={() => previewMutation.mutate()}
                  type="button"
                  variant="secondary"
                >
                  {previewMutation.isPending ? "Проверяем..." : "Проверить заявку"}
                </Button>
                <Button
                  disabled={createMutation.isPending || Boolean(selectedOffering && !previewIsFresh)}
                  leadingIcon={<Send className="h-4 w-4" />}
                  type="submit"
                >
                  {createMutation.isPending ? "Создаем..." : "Создать заявку"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <aside className="grid content-start gap-5">
          <Card>
            <CardHeader>
              <CardTitle>Войти в тикет</CardTitle>
              <CardDescription>Если заявка уже создана, откройте ее по ссылке и коду доступа.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              {selectedService || selectedOffering ? (
                <div className="rounded-[1rem] border border-border bg-surface-subtle px-4 py-3">
                  <p className="font-semibold text-slate-950">Безопасный preview</p>
                  {previewMutation.data ? (
                    <div className="mt-2 space-y-2">
                      <p>
                        {[previewMutation.data.service?.title, previewMutation.data.offering?.title]
                          .filter(Boolean)
                          .join(" / ") || "Каталог услуг пока не выбран."}
                      </p>
                      <div className="grid gap-1 text-xs text-slate-600">
                        {previewMutation.data.request_type_label ? (
                          <span>Тип: {previewMutation.data.request_type_label}</span>
                        ) : null}
                        {previewMutation.data.expected_first_response ? (
                          <span>Ответ: {previewMutation.data.expected_first_response}</span>
                        ) : null}
                        {previewMutation.data.expected_resolution ? (
                          <span>Решение: {previewMutation.data.expected_resolution}</span>
                        ) : null}
                        <span>{previewMutation.data.approval?.text ?? "Согласование будет определено автоматически."}</span>
                        <span>{previewMutation.data.diagnostics?.text ?? "Диагностика будет определена автоматически."}</span>
                      </div>
                      {previewMutation.data.next_action ? (
                        <p className="text-xs text-slate-600">{previewMutation.data.next_action}</p>
                      ) : null}
                      {previewMutation.data.warnings?.length ? (
                        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                          {previewMutation.data.warnings.join(" ")}
                        </div>
                      ) : null}
                      {previewMutation.data.blockers?.length ? (
                        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                          {previewMutation.data.blockers.join(" ")}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <p className="mt-1">
                      {[selectedService?.title, selectedOffering?.title].filter(Boolean).join(" / ") ||
                        "Каталог услуг пока не выбран."}
                    </p>
                  )}
                </div>
              ) : null}
              {ticketId ? (
                <>
                  <p className="font-semibold text-slate-950">Код доступа: {accessCode}</p>
                  <p>Сохраните код до завершения обращения.</p>
                  <Link
                    className="inline-flex h-11 w-full items-center justify-center rounded-pill border border-border bg-white px-4 text-sm font-semibold text-slate-700 transition-colors duration-200 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
                    to={`/app/ticket/${encodeURIComponent(ticketId)}?code=${encodeURIComponent(accessCode)}`}
                  >
                    Открыть тикет
                  </Link>
                </>
              ) : (
                <p>После создания заявки здесь появится код доступа и ссылка на чат.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </section>
    </main>
  );
}
