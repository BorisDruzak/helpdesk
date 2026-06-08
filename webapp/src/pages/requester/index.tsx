import { CheckCircle2, RefreshCw, RotateCcw, Send, Star } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  closeRequesterTicket,
  createRequesterTicket,
  fetchPublicFormPack,
  fetchRequesterBootstrap,
  fetchRequesterTicket,
  fetchRequesterTickets,
  fetchServiceCatalogCurrent,
  previewRequesterTicket,
  recordKnowledgeFeedback,
  reopenRequesterTicket,
  RequesterApiError,
  sendRequesterTicketMessage,
  suggestKnowledge,
  submitRequesterTicketFeedback,
} from "../../features/requester/api";
import type {
  AuthenticatedRequesterTicket,
  KnowledgeAttempt,
  KnowledgeSuggestResult,
  KnowledgeSuggestionItem,
  RequestFormDefinition,
  RequestFormField,
  RequesterBootstrap,
  RequesterDevice,
  RequesterTicketCreatePayload,
  RequesterTicketDetail,
  ServiceCatalogCurrent,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";

type FieldValues = Record<string, string | boolean>;

function deviceLabel(device: RequesterDevice): string {
  return device.hostname || device.asset_name || device.device_id;
}

function ticketStatus(ticket: AuthenticatedRequesterTicket): string {
  return ticket.requester_status_label || ticket.status_label || ticket.requester_status || ticket.status || "open";
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

function visibleKnowledgeSuggestions(
  suggestions: KnowledgeSuggestionItem[],
  rollout?: KnowledgeSuggestResult["rollout"] | null,
): KnowledgeSuggestionItem[] {
  return suggestions
    .filter((item) => rollout?.show_known_errors !== false || item.type !== "known_error")
    .map((item) => {
      const next = { ...item };
      if (rollout?.show_quality_badge === false) {
        delete next.quality_label;
      }
      if (rollout?.show_review_freshness === false) {
        delete next.freshness_label;
      }
      return next;
    });
}

function RequestFormFieldControl({
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
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <textarea
          aria-label={`Requester form field ${field.key}`}
          className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          placeholder={field.placeholder ?? ""}
          value={String(value ?? "")}
        />
      </label>
    );
  }
  if (field.type === "select" || field.type === "radio") {
    return (
      <label className="block text-sm font-semibold text-slate-700">
        {label}
        <select
          aria-label={`Requester form field ${field.key}`}
          className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
          onChange={(event) => onChange(event.currentTarget.value)}
          value={String(value ?? "")}
        >
          <option value="">Выберите...</option>
          {(field.options ?? []).map((option) => (
            <option key={option.value} value={option.value}>
              {option.label || option.value}
            </option>
          ))}
        </select>
      </label>
    );
  }
  if (field.type === "checkbox") {
    return (
      <label className="flex items-center gap-2 rounded-panel border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700">
        <input
          aria-label={`Requester form field ${field.key}`}
          checked={value === true}
          onChange={(event) => onChange(event.currentTarget.checked)}
          type="checkbox"
        />
        <span>{label}</span>
      </label>
    );
  }
  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <input
        aria-label={`Requester form field ${field.key}`}
        className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
        onChange={(event) => onChange(event.currentTarget.value)}
        placeholder={field.placeholder ?? ""}
        type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
        value={String(value ?? "")}
      />
    </label>
  );
}

export function RequesterWorkspacePage() {
  const [bootstrap, setBootstrap] = useState<RequesterBootstrap | null>(null);
  const [tickets, setTickets] = useState<AuthenticatedRequesterTicket[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [title, setTitle] = useState("Проверка рабочего места");
  const [description, setDescription] = useState("");
  const [catalog, setCatalog] = useState<ServiceCatalogCurrent | null>(null);
  const [forms, setForms] = useState<RequestFormDefinition[]>([]);
  const [formPackMeta, setFormPackMeta] = useState<{ pack_key: string; version: string } | null>(null);
  const [selectedServiceCode, setSelectedServiceCode] = useState("");
  const [selectedOfferingFullCode, setSelectedOfferingFullCode] = useState("");
  const [selectedFormKey, setSelectedFormKey] = useState("");
  const [fieldValues, setFieldValues] = useState<FieldValues>({});
  const [catalogNotice, setCatalogNotice] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<ServiceCatalogSafePreview | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [previewSubmitting, setPreviewSubmitting] = useState(false);
  const [knowledgeResult, setKnowledgeResult] = useState<KnowledgeSuggestResult | null>(null);
  const [knowledgeLoading, setKnowledgeLoading] = useState(false);
  const [knowledgeError, setKnowledgeError] = useState(false);
  const [openedKnowledgeId, setOpenedKnowledgeId] = useState<string | null>(null);
  const [knowledgeAttempts, setKnowledgeAttempts] = useState<KnowledgeAttempt[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdTicketId, setCreatedTicketId] = useState<string | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicketDetail, setSelectedTicketDetail] = useState<RequesterTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [messageText, setMessageText] = useState("");
  const [messageSending, setMessageSending] = useState(false);
  const [messageNotice, setMessageNotice] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [feedbackRating, setFeedbackRating] = useState(5);
  const [feedbackProblemResolved, setFeedbackProblemResolved] = useState(true);
  const [feedbackReason, setFeedbackReason] = useState("not_resolved");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackId, setFeedbackId] = useState<string | null>(null);
  const [reopenReason, setReopenReason] = useState("not_resolved");
  const [reopenComment, setReopenComment] = useState("");
  const [reopenAvailable, setReopenAvailable] = useState(false);

  const devices = bootstrap?.devices ?? [];
  const visibleTickets = tickets.length ? tickets : bootstrap?.recent_tickets ?? [];
  const profileName = bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || bootstrap?.profile?.email || "Пользователь";
  const services = catalog?.services ?? [];

  const selectedDevice = useMemo(
    () => devices.find((device) => device.device_id === selectedDeviceId) ?? devices[0] ?? null,
    [devices, selectedDeviceId],
  );
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
  const knowledgeKey = useMemo(
    () =>
      JSON.stringify({
        service_code: selectedService?.service_code,
        offering_full_code: selectedOffering?.full_code,
        form_key: selectedForm?.key,
        form_payload: visiblePayload,
        description: description.slice(0, 240),
      }),
    [description, selectedForm?.key, selectedOffering?.full_code, selectedService?.service_code, visiblePayload],
  );
  const currentPreviewKey = useMemo(
    () =>
      JSON.stringify({
        device_id: selectedDevice?.device_id,
        service_code: selectedService?.service_code,
        offering_full_code: selectedOffering?.full_code,
        form_key: selectedForm?.key,
        form_payload: visiblePayload,
        description,
      }),
    [description, selectedDevice?.device_id, selectedForm?.key, selectedOffering?.full_code, selectedService?.service_code, visiblePayload],
  );
  const selectedTicket = selectedTicketDetail?.ticket ?? null;
  const selectedTicketStatus = selectedTicket?.status ?? "";
  const canCloseSelectedTicket = selectedTicketStatus === "resolved";
  const canRateSelectedTicket = selectedTicketStatus === "resolved" || selectedTicketStatus === "closed";
  const canReopenSelectedTicket = canRateSelectedTicket && (reopenAvailable || feedbackRating <= 3 || !feedbackProblemResolved);
  const previewIsFresh =
    Boolean(selectedOffering) &&
    previewKey === currentPreviewKey &&
    Boolean(previewResult?.ok) &&
    !(previewResult?.blockers ?? []).length;
  const knowledgeRollout = knowledgeResult?.rollout;
  const knowledgeVisible = Boolean(selectedOffering && knowledgeRollout?.enabled !== false && knowledgeRollout?.show_before_form !== false);
  const knowledgeSuggestions = useMemo(
    () => visibleKnowledgeSuggestions(knowledgeResult?.suggestions ?? [], knowledgeRollout),
    [knowledgeResult?.suggestions, knowledgeRollout],
  );

  async function load() {
    setLoading(true);
    setError(null);
    setCatalogNotice(null);
    try {
      const nextBootstrap = await fetchRequesterBootstrap();
      const nextTickets = await fetchRequesterTickets();
      setBootstrap(nextBootstrap);
      setTickets(nextTickets);
      setSelectedDeviceId((current) => current || nextBootstrap.devices[0]?.device_id || "");
      try {
        const [nextForms, nextCatalog] = await Promise.all([fetchPublicFormPack(), fetchServiceCatalogCurrent()]);
        setForms(nextForms.forms ?? []);
        setFormPackMeta({ pack_key: nextForms.pack_key, version: nextForms.version });
        setCatalog(nextCatalog);
      } catch {
        setCatalogNotice("Каталог услуг временно недоступен. Можно создать обращение по теме и описанию.");
      }
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить кабинет");
    } finally {
      setLoading(false);
    }
  }

  async function refreshSelectedTicket(ticketId: string) {
    const [nextDetail, nextTickets] = await Promise.all([
      fetchRequesterTicket(ticketId),
      fetchRequesterTickets(),
    ]);
    setSelectedTicketDetail(nextDetail);
    setTickets(nextTickets);
  }

  useEffect(() => {
    void load();
  }, []);

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

  useEffect(() => {
    if (!selectedOffering) {
      setKnowledgeResult(null);
      setKnowledgeError(false);
      setKnowledgeLoading(false);
      return;
    }
    let canceled = false;
    setKnowledgeLoading(true);
    setKnowledgeError(false);
    void suggestKnowledge({
      service_code: selectedService?.service_code,
      offering_code: selectedOffering.full_code,
      request_template_key: selectedOffering.request_template_key ?? selectedForm?.key,
      query: description || selectedOffering.title || selectedService?.title || "",
      form_payload: visiblePayload,
      surface: "requester_portal",
      urgency: "normal",
      impact: "normal",
    })
      .then((result) => {
        if (!canceled) {
          setKnowledgeResult(result);
        }
      })
      .catch(() => {
        if (!canceled) {
          setKnowledgeResult(null);
          setKnowledgeError(true);
        }
      })
      .finally(() => {
        if (!canceled) {
          setKnowledgeLoading(false);
        }
      });
    return () => {
      canceled = true;
    };
  }, [description, knowledgeKey, selectedForm?.key, selectedOffering, selectedService?.service_code, selectedService?.title, visiblePayload]);

  function appendKnowledgeAttempt(item: KnowledgeSuggestionItem, result: KnowledgeAttempt["result"]) {
    const attempt: KnowledgeAttempt = {
      item_id: item.item_id,
      version_id: item.version_id ?? null,
      result,
      surface: "requester_portal",
      timestamp: new Date().toISOString(),
    };
    setKnowledgeAttempts((current) => [
      ...current.filter((entry) => entry.item_id !== item.item_id || entry.result !== result),
      attempt,
    ]);
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

  function buildCreatePayload(): RequesterTicketCreatePayload {
    if (!selectedDevice) {
      throw new Error("Выберите устройство");
    }
    if (!description.trim()) {
      throw new Error("Заполните описание");
    }
    const missing = missingRequiredFields(selectedForm, fieldValues);
    if (missing.length) {
      throw new Error(`Заполните обязательные поля: ${missing.join(", ")}`);
    }
    const payload: RequesterTicketCreatePayload = {
      device_id: selectedDevice.device_id,
      title: title.trim() || selectedForm?.title || selectedOffering?.title || "Проверка рабочего места",
      description: description.trim(),
      user_display_name: profileName,
      urgency: false,
      importance: false,
      urgency_reason: "Создано из кабинета заявителя",
      importance_reason: "Создано из кабинета заявителя",
      ...(selectedForm && formPackMeta
        ? {
            form_key: selectedForm.key,
            form_pack_key: formPackMeta.pack_key,
            form_pack_version: formPackMeta.version,
            form_payload: visiblePayload,
            ticket_type: selectedForm.request_kind || selectedForm.key,
            request_template_key: selectedOffering?.request_template_key ?? selectedForm.key,
            service_code: selectedService?.service_code,
            offering_code: selectedOffering?.offering_code,
            offering_full_code: selectedOffering?.full_code,
          }
        : {}),
    };
    if (knowledgeAttempts.length) {
      payload.knowledge_attempts = knowledgeAttempts;
    }
    return payload;
  }

  async function handlePreview() {
    setPreviewSubmitting(true);
    setError(null);
    setPreviewResult(null);
    try {
      const createPayload = buildCreatePayload();
      const result = await previewRequesterTicket({
        device_id: createPayload.device_id,
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
          requester_profile: {
            full_name: profileName,
            email: bootstrap?.profile?.email,
            phone: bootstrap?.profile?.phone,
          },
        },
        device_metadata: {
          device_id: selectedDevice?.device_id,
          hostname: selectedDevice?.hostname,
          os: selectedDevice?.os,
        },
      });
      setPreviewResult(result);
      setPreviewKey(currentPreviewKey);
      if ((result.blockers ?? []).length) {
        setError(result.blockers.join(" "));
      } else {
        setCatalogNotice((result.warnings ?? []).length ? `Preview рассчитан: ${result.warnings.join(" ")}` : "Preview рассчитан");
      }
    } catch (exc) {
      setPreviewKey("");
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось проверить обращение");
    } finally {
      setPreviewSubmitting(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedDevice || !description.trim()) {
      setError("Выберите устройство и заполните описание");
      return;
    }
    if (selectedOffering && !previewIsFresh) {
      setError("Сначала выполните безопасный preview заявки");
      return;
    }
    setSubmitting(true);
    setError(null);
    setCreatedTicketId(null);
    try {
      const result = await createRequesterTicket(buildCreatePayload());
      setCreatedTicketId(result.ticket_id);
      setDescription("");
      setPreviewKey("");
      setPreviewResult(null);
      setTickets(await fetchRequesterTickets());
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось создать обращение");
    } finally {
      setSubmitting(false);
    }
  }

  async function openTicket(ticketId: string) {
    setSelectedTicketId(ticketId);
    setSelectedTicketDetail(null);
    setDetailLoading(true);
    setMessageNotice(null);
    setActionNotice(null);
    setFeedbackId(null);
    setReopenAvailable(false);
    setError(null);
    try {
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить обращение");
    } finally {
      setDetailLoading(false);
    }
  }

  async function handleMessageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ticketId = selectedTicketId;
    const text = messageText.trim();
    if (!ticketId || !text) {
      return;
    }
    setMessageSending(true);
    setMessageNotice(null);
    setError(null);
    try {
      await sendRequesterTicketMessage(ticketId, text);
      setMessageText("");
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
      setMessageNotice("Сообщение отправлено");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось отправить сообщение");
    } finally {
      setMessageSending(false);
    }
  }

  async function handleCloseSelectedTicket() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      await closeRequesterTicket(ticketId);
      await refreshSelectedTicket(ticketId);
      setActionNotice("Решение подтверждено, обращение закрыто");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось закрыть обращение");
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleFeedbackSubmit() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      const result = await submitRequesterTicketFeedback(ticketId, {
        rating: feedbackRating,
        problem_resolved: feedbackProblemResolved,
        resolution_confirmed: feedbackProblemResolved,
        reason_codes: feedbackRating <= 3 || !feedbackProblemResolved ? [feedbackReason] : [],
        comment: feedbackComment.trim() || null,
        source_surface: "requester_portal",
      });
      setFeedbackId(result.feedback_id);
      setReopenAvailable(result.reopen_available);
      await refreshSelectedTicket(ticketId);
      setActionNotice(result.message || "Оценка сохранена");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось сохранить оценку");
    } finally {
      setActionSubmitting(false);
    }
  }

  async function handleReopenSelectedTicket() {
    const ticketId = selectedTicketId;
    if (!ticketId) {
      return;
    }
    setActionSubmitting(true);
    setActionNotice(null);
    setError(null);
    try {
      await reopenRequesterTicket(ticketId, {
        reason_code: reopenReason,
        reason_comment: reopenComment.trim() || feedbackComment.trim() || null,
        linked_feedback_id: feedbackId,
      });
      await refreshSelectedTicket(ticketId);
      setActionNotice("Обращение вернулось в работу");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось вернуть обращение в работу");
    } finally {
      setActionSubmitting(false);
    }
  }

  if (loading) {
    return <section className="workspace-page p-6 text-sm text-slate-500">Загружаем кабинет заявителя...</section>;
  }

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <p className="workspace-boot__eyebrow">Кабинет заявителя</p>
          <h1>Мои обращения</h1>
          <p>Профиль {profileName}. Доступны только устройства и обращения, связанные с вашей учетной записью.</p>
        </div>
        <dl className="workspace-page__stats">
          <div>
            <dt>Устройства</dt>
            <dd>{devices.length}</dd>
          </div>
          <div>
            <dt>Открытые</dt>
            <dd>{bootstrap?.open_ticket_count ?? visibleTickets.length}</dd>
          </div>
          <div>
            <dt>Действия</dt>
            <dd>{bootstrap?.tickets_requiring_user_action_count ?? 0}</dd>
          </div>
        </dl>
      </header>

      {error ? <div className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
      {createdTicketId ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          Создано обращение {createdTicketId}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
        <section className="support-workspace__panel">
          <div className="support-workspace__panel-head">
            <div>
              <p className="workspace-boot__eyebrow">Обращения</p>
              <h2 className="text-lg font-semibold text-slate-950">Последние заявки</h2>
            </div>
            <button className="inline-flex items-center gap-2 rounded-panel border px-3 py-2 text-sm font-semibold" onClick={() => void load()} type="button">
              <RefreshCw className="h-4 w-4" />
              Обновить
            </button>
          </div>
          <div className="mt-4 divide-y divide-slate-100">
            {visibleTickets.length ? (
              visibleTickets.map((ticket) => (
                <button
                  aria-label={`Open requester ticket ${ticket.ticket_id}`}
                  className={`block w-full py-3 text-left ${selectedTicketId === ticket.ticket_id ? "bg-slate-50" : ""}`}
                  key={ticket.ticket_id}
                  onClick={() => void openTicket(ticket.ticket_id)}
                  type="button"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-slate-950">{ticket.ticket_id}</span>
                    <span className="rounded-panel bg-slate-100 px-2 py-1 text-xs text-slate-600">{ticketStatus(ticket)}</span>
                  </div>
                  <h3 className="mt-1 text-sm font-semibold text-slate-800">{ticket.title || "Без темы"}</h3>
                  <p className="mt-1 line-clamp-2 text-sm text-slate-500">{ticket.description || "Описание не указано"}</p>
                </button>
              ))
            ) : (
              <p className="py-6 text-sm text-slate-500">Обращений пока нет.</p>
            )}
          </div>
        </section>

          {selectedTicketId ? (
            <section className="support-workspace__panel">
              <div className="support-workspace__panel-head">
                <div>
                  <p className="workspace-boot__eyebrow">Диалог</p>
                  <h2 className="text-lg font-semibold text-slate-950">
                    {selectedTicketDetail?.ticket.title || selectedTicketId}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {selectedTicketDetail?.ticket.description || (detailLoading ? "Загружаем обращение..." : "Описание не указано")}
                  </p>
                </div>
              </div>

              <div className="mt-4 space-y-3">
                {detailLoading ? (
                  <p className="text-sm text-slate-500">Загружаем историю...</p>
                ) : selectedTicketDetail?.messages?.length ? (
                  selectedTicketDetail.messages.map((message) => (
                    <div className="rounded-panel border border-slate-200 p-3" key={message.message_id || message.event_id || message.ts}>
                      <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                        <span>{message.from_role === "support" ? "Поддержка" : "Заявитель"}</span>
                        <span>{message.ts || message.created_at || ""}</span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{message.text || ""}</p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">Сообщений пока нет.</p>
                )}
              </div>

              {selectedTicket ? (
                <div className="mt-4 grid gap-3 rounded-panel border border-slate-200 bg-slate-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">Действия по обращению</p>
                      <p className="text-xs text-slate-500">
                        Статус: {selectedTicket.requester_status_label || selectedTicket.status_label || selectedTicket.status}
                      </p>
                    </div>
                    {canCloseSelectedTicket ? (
                      <button
                        aria-label="Close requester ticket"
                        className="inline-flex items-center justify-center gap-2 rounded-panel bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                        disabled={actionSubmitting}
                        onClick={() => void handleCloseSelectedTicket()}
                        type="button"
                      >
                        <CheckCircle2 className="h-4 w-4" />
                        Подтвердить и закрыть
                      </button>
                    ) : null}
                  </div>

                  {canRateSelectedTicket ? (
                    <div className="grid gap-3 border-t border-slate-200 pt-3">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <label className="block text-sm font-semibold text-slate-700">
                          Оценка
                          <select
                            aria-label="Requester feedback rating"
                            className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => setFeedbackRating(Number(event.target.value))}
                            value={feedbackRating}
                          >
                            {[5, 4, 3, 2, 1].map((value) => (
                              <option key={value} value={value}>
                                {value}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="flex items-center gap-2 self-end text-sm font-semibold text-slate-700">
                          <input
                            aria-label="Requester problem resolved"
                            checked={feedbackProblemResolved}
                            onChange={(event) => {
                              setFeedbackProblemResolved(event.target.checked);
                              if (!event.target.checked) {
                                setReopenAvailable(true);
                              }
                            }}
                            type="checkbox"
                          />
                          Проблема решена
                        </label>
                      </div>
                      {feedbackRating <= 3 || !feedbackProblemResolved ? (
                        <label className="block text-sm font-semibold text-slate-700">
                          Причина
                          <select
                            className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => {
                              setFeedbackReason(event.target.value);
                              setReopenReason(event.target.value);
                            }}
                            value={feedbackReason}
                          >
                            <option value="not_resolved">Не решено</option>
                            <option value="problem_returned">Проблема вернулась</option>
                            <option value="slow_resolution">Долгое решение</option>
                            <option value="poor_communication">Недостаточно коммуникации</option>
                            <option value="other">Другое</option>
                          </select>
                        </label>
                      ) : null}
                      <label className="block text-sm font-semibold text-slate-700">
                        Комментарий
                        <textarea
                          className="mt-1 min-h-20 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                          onChange={(event) => setFeedbackComment(event.target.value)}
                          value={feedbackComment}
                        />
                      </label>
                      <div className="flex flex-wrap gap-2">
                        <button
                          aria-label="Submit requester feedback"
                          className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                          disabled={actionSubmitting || (feedbackReason === "other" && !feedbackComment.trim())}
                          onClick={() => void handleFeedbackSubmit()}
                          type="button"
                        >
                          <Star className="h-4 w-4" />
                          Отправить оценку
                        </button>
                        {canReopenSelectedTicket ? (
                          <button
                            aria-label="Reopen requester ticket"
                            className="inline-flex items-center justify-center gap-2 rounded-panel border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900 disabled:cursor-not-allowed disabled:bg-slate-100"
                            disabled={actionSubmitting || (reopenReason === "other" && !reopenComment.trim() && !feedbackComment.trim())}
                            onClick={() => void handleReopenSelectedTicket()}
                            type="button"
                          >
                            <RotateCcw className="h-4 w-4" />
                            Вернуть в работу
                          </button>
                        ) : null}
                      </div>
                      {canReopenSelectedTicket ? (
                        <label className="block text-sm font-semibold text-slate-700">
                          Комментарий для повторного открытия
                          <textarea
                            className="mt-1 min-h-16 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                            onChange={(event) => setReopenComment(event.target.value)}
                            value={reopenComment}
                          />
                        </label>
                      ) : null}
                    </div>
                  ) : null}
                  {actionNotice ? <p className="text-sm text-emerald-700">{actionNotice}</p> : null}
                </div>
              ) : null}

              <form className="mt-4 space-y-3" onSubmit={(event) => void handleMessageSubmit(event)}>
                <label className="block text-sm font-semibold text-slate-700">
                  Ответ
                  <textarea
                    aria-label="Requester message"
                    className="mt-1 min-h-24 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => setMessageText(event.target.value)}
                    value={messageText}
                  />
                </label>
                {messageNotice ? <p className="text-sm text-emerald-700">{messageNotice}</p> : null}
                <button
                  aria-label="Send requester message"
                  className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={messageSending || !selectedTicketId || !messageText.trim()}
                  type="submit"
                >
                  <Send className="h-4 w-4" />
                  {messageSending ? "Отправляем..." : "Отправить"}
                </button>
              </form>
            </section>
          ) : null}
        </div>

        <aside className="space-y-5">
          <section className="support-workspace__panel">
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Устройства</p>
                <h2 className="text-lg font-semibold text-slate-950">Мои устройства</h2>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              {devices.length ? (
                devices.map((device) => (
                  <label className="flex cursor-pointer items-start gap-3 rounded-panel border border-slate-200 p-3 text-sm" key={device.device_id}>
                    <input
                      checked={(selectedDevice?.device_id ?? "") === device.device_id}
                      className="mt-1"
                      name="requester-device"
                      onChange={() => setSelectedDeviceId(device.device_id)}
                      type="radio"
                    />
                    <span>
                      <span className="block font-semibold text-slate-900">{deviceLabel(device)}</span>
                      <span className="block text-xs text-slate-500">{device.os || "OS не указан"} · agent {device.agent_version || "unknown"}</span>
                    </span>
                  </label>
                ))
              ) : (
                <p className="text-sm text-slate-500">Зарегистрированных устройств пока нет.</p>
              )}
            </div>
          </section>

          <form className="support-workspace__panel space-y-3" onSubmit={(event) => void handleSubmit(event)}>
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Новая заявка</p>
                <h2 className="text-lg font-semibold text-slate-950">Создать обращение</h2>
              </div>
            </div>
            {catalogNotice ? (
              <div
                className={
                  catalogNotice.startsWith("Каталог услуг временно")
                    ? "rounded-panel border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800"
                    : "rounded-panel border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700"
                }
              >
                {catalogNotice}
              </div>
            ) : null}
            {services.length ? (
              <div className="grid gap-3">
                <label className="block text-sm font-semibold text-slate-700">
                  Услуга
                  <select
                    aria-label="Requester service"
                    className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => {
                      const nextCode = event.currentTarget.value;
                      setSelectedServiceCode(nextCode);
                      const nextService = services.find((service) => service.service_code === nextCode);
                      setSelectedOfferingFullCode(nextService?.offerings[0]?.full_code ?? "");
                      setPreviewKey("");
                      setPreviewResult(null);
                    }}
                    value={selectedService?.service_code ?? ""}
                  >
                    {services.map((service) => (
                      <option key={service.service_code} value={service.service_code}>
                        {service.title || service.service_code}
                      </option>
                    ))}
                  </select>
                </label>
                {selectedService?.offerings.length ? (
                  <label className="block text-sm font-semibold text-slate-700">
                    Тип обращения
                    <select
                      aria-label="Requester offering"
                      className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                      onChange={(event) => {
                        setSelectedOfferingFullCode(event.currentTarget.value);
                        setPreviewKey("");
                        setPreviewResult(null);
                      }}
                      value={selectedOffering?.full_code ?? ""}
                    >
                      {selectedService.offerings.map((offering) => (
                        <option key={offering.full_code} value={offering.full_code}>
                          {offering.title || offering.offering_code}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {selectedOffering ? (
                  <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    <p className="font-semibold text-slate-900">{selectedOffering.title}</p>
                    {selectedOffering.description ? <p className="mt-1">{selectedOffering.description}</p> : null}
                    <p className="mt-1 text-xs">
                      {[
                        selectedOffering.expected_response ? `Ответ: ${selectedOffering.expected_response}` : null,
                        selectedOffering.expected_resolution ? `Решение: ${selectedOffering.expected_resolution}` : null,
                        selectedOffering.approval_required ? "Потребуется согласование" : null,
                        selectedOffering.diagnostic_consent_required ? "Потребуется согласие на диагностику" : null,
                      ]
                        .filter(Boolean)
                      .join(" · ")}
                    </p>
                  </div>
                ) : null}
                {knowledgeVisible ? (
                  <div className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold text-slate-900">Возможно, поможет</p>
                      {knowledgeLoading ? <span className="text-xs text-slate-500">Ищем...</span> : null}
                    </div>
                    {knowledgeError ? (
                      <p className="mt-2 text-xs text-amber-700">Инструкции временно недоступны.</p>
                    ) : null}
                    {knowledgeSuggestions.length ? (
                      <div className="mt-2 grid gap-2">
                        {knowledgeSuggestions.map((item) => (
                          <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2" key={item.item_id}>
                            <p className="font-semibold text-slate-900">{item.title}</p>
                            {item.summary ? <p className="mt-1 text-xs text-slate-600">{item.summary}</p> : null}
                            {item.quality_label || item.freshness_label ? (
                              <p className="mt-1 text-[11px] font-semibold text-slate-500">
                                {[item.quality_label, item.freshness_label].filter(Boolean).join(" · ")}
                              </p>
                            ) : null}
                            {openedKnowledgeId === item.item_id && item.snippet ? (
                              <p className="mt-2 rounded-panel bg-white px-3 py-2 text-xs text-slate-700">{item.snippet}</p>
                            ) : null}
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                aria-label="Open requester knowledge suggestion"
                                className="rounded-panel border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                                onClick={() => {
                                  setOpenedKnowledgeId((current) => (current === item.item_id ? null : item.item_id));
                                  recordKnowledgeAttempt(item, "viewed");
                                }}
                                type="button"
                              >
                                {openedKnowledgeId === item.item_id ? "Скрыть" : "Открыть"}
                              </button>
                              <button
                                aria-label="Mark requester knowledge suggestion helpful"
                                className="rounded-panel border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800"
                                onClick={() => recordKnowledgeAttempt(item, "deflected")}
                                type="button"
                              >
                                Помогло
                              </button>
                              <button
                                aria-label="Mark requester knowledge suggestion not helpful"
                                className="rounded-panel border border-slate-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800"
                                onClick={() => recordKnowledgeAttempt(item, "not_helpful")}
                                type="button"
                              >
                                Не помогло
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : !knowledgeLoading && !knowledgeError ? (
                      <p className="mt-2 text-xs text-slate-500">Подходящих опубликованных инструкций пока нет.</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}
            {forms.length ? (
              <div className="grid gap-3">
                <label className="block text-sm font-semibold text-slate-700">
                  Форма обращения
                  <select
                    aria-label="Requester form"
                    className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                    onChange={(event) => {
                      setSelectedFormKey(event.currentTarget.value);
                      setPreviewKey("");
                      setPreviewResult(null);
                    }}
                    value={selectedForm?.key ?? ""}
                  >
                    {forms.map((form) => (
                      <option key={form.key} value={form.key}>
                        {form.title || form.key}
                      </option>
                    ))}
                  </select>
                </label>
                {visibleFields.map((field) => (
                  <RequestFormFieldControl
                    field={field}
                    key={field.key}
                    onChange={(value) => {
                      setFieldValues((current) => ({ ...current, [field.key]: value }));
                      setPreviewKey("");
                      setPreviewResult(null);
                    }}
                    value={fieldValues[field.key] ?? (field.type === "checkbox" ? false : "")}
                  />
                ))}
              </div>
            ) : null}
            <label className="block text-sm font-semibold text-slate-700">
              Тема
              <input className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal" onChange={(event) => setTitle(event.target.value)} value={title} />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Описание
              <textarea
                className="mt-1 min-h-32 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setDescription(event.target.value)}
                value={description}
              />
            </label>
            {previewResult ? (
              <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
                <p className="font-semibold text-slate-900">Безопасный preview</p>
                <p>{[previewResult.service?.title, previewResult.offering?.title].filter(Boolean).join(" / ")}</p>
                {previewResult.request_type_label ? <p>Тип: {previewResult.request_type_label}</p> : null}
                {previewResult.expected_first_response ? <p>Ответ: {previewResult.expected_first_response}</p> : null}
                {previewResult.expected_resolution ? <p>Решение: {previewResult.expected_resolution}</p> : null}
                {previewResult.approval?.text ? <p>{previewResult.approval.text}</p> : null}
                {previewResult.diagnostics?.text ? <p>{previewResult.diagnostics.text}</p> : null}
                {previewResult.blockers?.length ? <p className="text-rose-700">{previewResult.blockers.join(" ")}</p> : null}
              </div>
            ) : null}
            <div className="grid gap-2">
              <button
                aria-label="Preview requester ticket"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                disabled={previewSubmitting || !selectedDevice || !description.trim() || !selectedOffering}
                onClick={() => void handlePreview()}
                type="button"
              >
                {previewSubmitting ? "Проверяем..." : "Проверить заявку"}
              </button>
              <button
                aria-label="Create requester ticket"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={submitting || !selectedDevice || !description.trim() || Boolean(selectedOffering && !previewIsFresh)}
                type="submit"
              >
                <Send className="h-4 w-4" />
                {submitting ? "Создаем..." : "Создать обращение"}
              </button>
            </div>
          </form>
        </aside>
      </div>
    </section>
  );
}
