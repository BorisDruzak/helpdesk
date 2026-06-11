import { CheckCircle2, Link2, Paperclip, RefreshCw, RotateCcw, Send, Star, X } from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  approveRequesterConsent,
  closeRequesterTicket,
  claimPublicRequesterTicket,
  createRequesterTicket,
  denyRequesterConsent,
  fetchPublicFormPack,
  fetchRequesterBootstrap,
  fetchRequesterConsents,
  fetchRequesterDevice,
  fetchRequesterProfile,
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
  uploadRequesterTicketAttachment,
} from "../../features/requester/api";
import type {
  AuthenticatedRequesterTicket,
  KnowledgeAttempt,
  KnowledgeSuggestResult,
  KnowledgeSuggestionItem,
  RequestFormDefinition,
  RequestFormField,
  RequesterBootstrap,
  RequesterConsent,
  RequesterDevice,
  RequesterDeviceDetail,
  RequesterProfileDetail,
  RequesterTicketCreatePayload,
  RequesterTicketDetail,
  ServiceCatalogCurrent,
  ServiceCatalogSafePreview,
} from "../../features/requester/types";

type FieldValues = Record<string, string | boolean>;

type PendingAttachment = {
  artifact_id: string;
  name: string;
  url?: string | null;
  mime_type?: string | null;
  kind?: string | null;
};

function deviceLabel(device: RequesterDevice): string {
  return device.hostname || device.asset_name || device.device_id;
}

function relationshipLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    primary_user: "Основной пользователь",
    responsible: "Ответственный",
    owner: "Владелец",
    shared_user: "Общий доступ",
    temporary_user: "Временный пользователь",
  };
  return labels[value || ""] || value || "Связь не указана";
}

function ticketStatus(ticket: AuthenticatedRequesterTicket): string {
  return ticket.requester_status_label || ticket.status_label || ticket.requester_status || ticket.status || "open";
}

function consentRiskLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    diagnostic: "Диагностика",
    remote_view: "Просмотр экрана",
    remote_control: "Удаленное управление",
    remote_admin: "Административный доступ",
  };
  return labels[value || ""] || value || "Требуется решение";
}

function consentSubjectLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    diagnostic: "Диагностика",
    operation: "Операция",
    remote_assist: "Удаленная помощь",
    tool_run: "Запуск инструмента",
  };
  return labels[value || ""] || value || "Запрос согласия";
}

function formatConsentExpiresAt(value?: string | null): string | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
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
  const [consents, setConsents] = useState<RequesterConsent[]>([]);
  const [consentSubmittingId, setConsentSubmittingId] = useState<string | null>(null);
  const [consentNotice, setConsentNotice] = useState<string | null>(null);
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
  const [selectedDeviceDetail, setSelectedDeviceDetail] = useState<RequesterDeviceDetail | null>(null);
  const [deviceDetailLoading, setDeviceDetailLoading] = useState(false);
  const [deviceDetailError, setDeviceDetailError] = useState<string | null>(null);
  const [profileDetail, setProfileDetail] = useState<RequesterProfileDetail | null>(null);
  const [profileDetailLoading, setProfileDetailLoading] = useState(false);
  const [profileDetailError, setProfileDetailError] = useState<string | null>(null);
  const [claimTicketId, setClaimTicketId] = useState("");
  const [claimCode, setClaimCode] = useState("");
  const [claimSubmitting, setClaimSubmitting] = useState(false);
  const [claimNotice, setClaimNotice] = useState<string | null>(null);
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);
  const [selectedTicketDetail, setSelectedTicketDetail] = useState<RequesterTicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [messageText, setMessageText] = useState("");
  const [messageSending, setMessageSending] = useState(false);
  const [attachmentUploading, setAttachmentUploading] = useState(false);
  const [pendingAttachments, setPendingAttachments] = useState<PendingAttachment[]>([]);
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
  const attachmentInputRef = useRef<HTMLInputElement | null>(null);

  const devices = bootstrap?.devices ?? [];
  const visibleTickets = tickets.length ? tickets : bootstrap?.recent_tickets ?? [];
  const pendingConsents = consents.filter((consent) => consent.status === "pending");
  const actionCount = (bootstrap?.tickets_requiring_user_action_count ?? 0) + pendingConsents.length;
  const profileName = bootstrap?.profile?.display_name || bootstrap?.profile?.full_name || bootstrap?.profile?.email || "Пользователь";
  const services = catalog?.services ?? [];
  const noDeviceCreateEnabled = bootstrap?.feature_flags?.requester_no_device_create === true;

  const selectedDevice = useMemo(
    () => devices.find((device) => device.device_id === selectedDeviceId) ?? devices[0] ?? null,
    [devices, selectedDeviceId],
  );
  const canCreateForCurrentScope = Boolean(selectedDevice) || noDeviceCreateEnabled;
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
      const [nextBootstrap, nextTickets] = await Promise.all([fetchRequesterBootstrap(), fetchRequesterTickets()]);
      setBootstrap(nextBootstrap);
      setTickets(nextTickets);
      setSelectedDeviceId((current) => current || nextBootstrap.devices[0]?.device_id || "");
      try {
        setConsents(await fetchRequesterConsents());
      } catch {
        setConsents([]);
      }
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

  async function handleConsentDecision(consent: RequesterConsent, decision: "approved" | "denied") {
    setConsentSubmittingId(consent.consent_id);
    setConsentNotice(null);
    setError(null);
    try {
      if (decision === "approved") {
        await approveRequesterConsent(consent.consent_id);
      } else {
        await denyRequesterConsent(consent.consent_id, "requester_denied");
      }
      setConsentNotice(decision === "approved" ? "Согласие подтверждено" : "Согласие отклонено");
      const [nextBootstrap, nextTickets, nextConsents] = await Promise.all([
        fetchRequesterBootstrap(),
        fetchRequesterTickets(),
        fetchRequesterConsents(),
      ]);
      setBootstrap(nextBootstrap);
      setTickets(nextTickets);
      setConsents(nextConsents);
      if (selectedTicketId) {
        setSelectedTicketDetail(await fetchRequesterTicket(selectedTicketId));
      }
    } catch (exc) {
      setError(exc instanceof RequesterApiError || exc instanceof Error ? exc.message : "Не удалось сохранить решение");
    } finally {
      setConsentSubmittingId(null);
    }
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

  async function openDeviceDetail(deviceId: string) {
    setSelectedDeviceId(deviceId);
    setDeviceDetailLoading(true);
    setDeviceDetailError(null);
    try {
      setSelectedDeviceDetail(await fetchRequesterDevice(deviceId));
    } catch (exc) {
      setSelectedDeviceDetail(null);
      setDeviceDetailError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить устройство");
    } finally {
      setDeviceDetailLoading(false);
    }
  }

  async function openProfileDetail() {
    setProfileDetailLoading(true);
    setProfileDetailError(null);
    try {
      setProfileDetail(await fetchRequesterProfile());
    } catch (exc) {
      setProfileDetail(null);
      setProfileDetailError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить профиль");
    } finally {
      setProfileDetailLoading(false);
    }
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
    if (!canCreateForCurrentScope) {
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
    if (selectedDevice?.device_id) {
      payload.device_id = selectedDevice.device_id;
    }
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
        ...(createPayload.device_id ? { device_id: createPayload.device_id } : {}),
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
        ...(selectedDevice
          ? {
              device_metadata: {
                device_id: selectedDevice.device_id,
                hostname: selectedDevice.hostname,
                os: selectedDevice.os,
              },
            }
          : {}),
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
    if (!canCreateForCurrentScope || !description.trim()) {
      setError(canCreateForCurrentScope ? "Заполните описание" : "Выберите устройство и заполните описание");
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

  async function handleClaimPublicTicket(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextTicketId = claimTicketId.trim();
    const nextCode = claimCode.trim();
    if (!nextTicketId || !nextCode) {
      setClaimNotice(null);
      setError("Укажите номер заявки и код доступа");
      return;
    }
    setClaimSubmitting(true);
    setClaimNotice(null);
    setError(null);
    try {
      const result = await claimPublicRequesterTicket(nextTicketId, nextCode);
      setClaimTicketId("");
      setClaimCode("");
      setClaimNotice("Обращение привязано");
      setTickets(await fetchRequesterTickets());
      await openTicket(result.ticket_id);
    } catch (exc) {
      if (exc instanceof RequesterApiError && exc.details === "REQUESTER_IDENTITY_REQUIRED") {
        setError("Для привязки обращения нужен связанный профиль пользователя. Обратитесь к администратору для привязки учетной записи.");
      } else {
        setError(exc instanceof RequesterApiError ? exc.message : "Не удалось привязать обращение");
      }
    } finally {
      setClaimSubmitting(false);
    }
  }

  async function openTicket(ticketId: string) {
    setSelectedTicketId(ticketId);
    setSelectedTicketDetail(null);
    setDetailLoading(true);
    setMessageNotice(null);
    setActionNotice(null);
    setPendingAttachments([]);
    setMessageText("");
    if (attachmentInputRef.current) {
      attachmentInputRef.current.value = "";
    }
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
    const attachmentRefs = pendingAttachments.map((attachment) => attachment.artifact_id);
    if (!ticketId || (!text && !attachmentRefs.length)) {
      return;
    }
    setMessageSending(true);
    setMessageNotice(null);
    setError(null);
    try {
      await sendRequesterTicketMessage(ticketId, text, attachmentRefs);
      setMessageText("");
      setPendingAttachments([]);
      if (attachmentInputRef.current) {
        attachmentInputRef.current.value = "";
      }
      setSelectedTicketDetail(await fetchRequesterTicket(ticketId));
      setMessageNotice("Сообщение отправлено");
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось отправить сообщение");
    } finally {
      setMessageSending(false);
    }
  }

  async function handleAttachmentChange(event: ChangeEvent<HTMLInputElement>) {
    const ticketId = selectedTicketId;
    const input = event.currentTarget;
    const files = Array.from(input.files ?? []);
    if (!ticketId || !files.length) {
      return;
    }
    setAttachmentUploading(true);
    setMessageNotice(null);
    setError(null);
    try {
      const uploaded = await Promise.all(files.map((file) => uploadRequesterTicketAttachment(ticketId, file)));
      setPendingAttachments((current) => [
        ...current,
        ...uploaded.map((item, index) => ({
          artifact_id: item.artifact_id,
          name: files[index]?.name || item.filename || item.artifact_id,
          url: item.url,
          mime_type: item.mime_type,
          kind: item.kind,
        })),
      ]);
    } catch (exc) {
      setError(exc instanceof RequesterApiError ? exc.message : "Не удалось загрузить вложение");
    } finally {
      setAttachmentUploading(false);
      input.value = "";
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
            <dd>{actionCount}</dd>
          </div>
        </dl>
      </header>

      {error ? <div className="rounded-panel border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div> : null}
      {consentNotice ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {consentNotice}
        </div>
      ) : null}
      {createdTicketId ? (
        <div className="rounded-panel border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          Создано обращение {createdTicketId}
        </div>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          {pendingConsents.length ? (
            <section aria-label="Requester pending consents" className="support-workspace__panel">
              <div className="support-workspace__panel-head">
                <div>
                  <p className="support-workspace__eyebrow">Согласие пользователя</p>
                  <h2>Ожидают вашего подтверждения</h2>
                </div>
                <span className="rounded-panel bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-800">
                  {pendingConsents.length}
                </span>
              </div>
              <div className="mt-4 grid gap-3">
                {pendingConsents.map((consent) => {
                  const expiresAt = formatConsentExpiresAt(consent.expires_at);
                  return (
                    <article className="rounded-panel border border-amber-200 bg-amber-50 px-4 py-3" key={consent.consent_id}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-xs font-semibold uppercase text-amber-700">
                            {consentSubjectLabel(consent.subject_type)} · {consentRiskLabel(consent.risk_level)}
                          </p>
                          <h3 className="mt-1 break-words text-sm font-semibold text-slate-950">
                            {consent.title || "Требуется ваше согласие"}
                          </h3>
                          {consent.description ? (
                            <p className="mt-1 break-words text-sm text-slate-700">{consent.description}</p>
                          ) : null}
                          <p className="mt-2 text-xs text-slate-600">
                            {consent.ticket_id ? `Обращение: ${consent.ticket_id}` : "Обращение не указано"}
                            {consent.device_id ? ` · Устройство: ${consent.device_id}` : ""}
                            {expiresAt ? ` · До: ${expiresAt}` : ""}
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <button
                            aria-label={`Deny requester consent ${consent.consent_id}`}
                            className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                            disabled={consentSubmittingId === consent.consent_id}
                            onClick={() => void handleConsentDecision(consent, "denied")}
                            type="button"
                          >
                            <X className="h-4 w-4" />
                            Отклонить
                          </button>
                          <button
                            aria-label={`Approve requester consent ${consent.consent_id}`}
                            className="inline-flex items-center justify-center gap-2 rounded-panel bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                            disabled={consentSubmittingId === consent.consent_id}
                            onClick={() => void handleConsentDecision(consent, "approved")}
                            type="button"
                          >
                            <CheckCircle2 className="h-4 w-4" />
                            Разрешить
                          </button>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          ) : null}
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
                      {message.attachments?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {message.attachments.map((attachment) => (
                            <a
                              className="inline-flex items-center gap-2 rounded-panel border border-slate-200 bg-white px-2 py-1 text-xs font-semibold text-brand-700"
                              href={attachment.url || `/api/artifacts/${encodeURIComponent(attachment.artifact_id)}/download`}
                              key={attachment.artifact_id}
                              rel="noreferrer"
                              target="_blank"
                            >
                              <Paperclip className="h-3.5 w-3.5" />
                              {attachment.name || attachment.artifact_id}
                            </a>
                          ))}
                        </div>
                      ) : null}
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
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    aria-label="Attach requester file"
                    className="sr-only"
                    disabled={attachmentUploading || messageSending || !selectedTicketId}
                    multiple
                    onChange={(event) => void handleAttachmentChange(event)}
                    ref={attachmentInputRef}
                    type="file"
                  />
                  <button
                    aria-label="Attach requester file button"
                    className="inline-flex items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                    disabled={attachmentUploading || messageSending || !selectedTicketId}
                    onClick={() => attachmentInputRef.current?.click()}
                    type="button"
                  >
                    <Paperclip className="h-4 w-4" />
                    {attachmentUploading ? "Загружаем..." : "Вложить файл"}
                  </button>
                </div>
                {pendingAttachments.length ? (
                  <div className="flex flex-wrap gap-2">
                    {pendingAttachments.map((attachment) => (
                      <span
                        className="inline-flex items-center gap-2 rounded-panel border border-slate-200 bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-700"
                        key={attachment.artifact_id}
                      >
                        <Paperclip className="h-3.5 w-3.5" />
                        {attachment.name}
                        <button
                          aria-label={`Remove requester attachment ${attachment.name}`}
                          className="inline-flex h-5 w-5 items-center justify-center rounded-full text-slate-500 hover:bg-slate-200"
                          onClick={() =>
                            setPendingAttachments((current) =>
                              current.filter((item) => item.artifact_id !== attachment.artifact_id),
                            )
                          }
                          type="button"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null}
                {messageNotice ? <p className="text-sm text-emerald-700">{messageNotice}</p> : null}
                <button
                  aria-label="Send requester message"
                  className="inline-flex items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                  disabled={
                    messageSending ||
                    attachmentUploading ||
                    !selectedTicketId ||
                    (!messageText.trim() && !pendingAttachments.length)
                  }
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
                <p className="workspace-boot__eyebrow">Профиль</p>
                <h2 className="text-lg font-semibold text-slate-950">Мой профиль</h2>
              </div>
            </div>
            <div className="mt-4 grid gap-3 text-sm text-slate-700">
              <div>
                <p className="break-words font-semibold text-slate-950">{profileName}</p>
                {bootstrap?.profile?.email ? <p className="break-words text-slate-500">{bootstrap.profile.email}</p> : null}
              </div>
              <button
                aria-label="Open requester profile detail"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                disabled={profileDetailLoading}
                onClick={() => void openProfileDetail()}
                type="button"
              >
                <Link2 className="h-4 w-4" />
                {profileDetailLoading ? "Загружаем..." : "Подробнее"}
              </button>
            </div>
            {profileDetailError ? <p className="mt-3 text-sm text-rose-700">{profileDetailError}</p> : null}
            {profileDetail ? (
              <div className="mt-4 rounded-panel border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <p className="font-semibold text-slate-950">Профиль заявителя</p>
                <dl className="mt-3 grid gap-2">
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Имя</dt>
                    <dd className="break-words font-semibold text-slate-900">
                      {profileDetail.profile?.full_name || profileDetail.profile?.display_name || profileName}
                    </dd>
                  </div>
                  {profileDetail.profile?.email ? (
                    <div>
                      <dt className="text-xs font-semibold uppercase text-slate-500">Email</dt>
                      <dd className="break-words">{profileDetail.profile.email}</dd>
                    </div>
                  ) : null}
                  {profileDetail.profile?.phone ? (
                    <div>
                      <dt className="text-xs font-semibold uppercase text-slate-500">Телефон</dt>
                      <dd className="break-words">{profileDetail.profile.phone}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Статус</dt>
                    <dd>{profileDetail.profile?.status || "profile not linked"}</dd>
                  </div>
                </dl>
                <p className="mt-3 rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                  Данные профиля доступны только для чтения.
                </p>
                {profileDetail.identities.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Идентификаторы</p>
                    <div className="mt-2 grid gap-2">
                      {profileDetail.identities.map((identity) => (
                        <div
                          className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
                          key={identity.identity_id || `${identity.provider}:${identity.identifier}`}
                        >
                          <span className="block font-semibold text-slate-900">{identity.provider}</span>
                          <span className="block break-words">{identity.identifier}</span>
                          <span className="block text-slate-500">{identity.verified ? "verified" : "not verified"}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
                {profileDetail.devices.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Устройства профиля</p>
                    <div className="mt-2 grid gap-2">
                      {profileDetail.devices.map((device) => (
                        <span
                          className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-900"
                          key={device.device_id}
                        >
                          {deviceLabel(device)}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

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
                  <div className="rounded-panel border border-slate-200 p-3 text-sm" key={device.device_id}>
                    <label className="flex cursor-pointer items-start gap-3">
                      <input
                        checked={(selectedDevice?.device_id ?? "") === device.device_id}
                        className="mt-1"
                        name="requester-device"
                        onChange={() => setSelectedDeviceId(device.device_id)}
                        type="radio"
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block break-words font-semibold text-slate-900">{deviceLabel(device)}</span>
                        <span className="block break-words text-xs text-slate-500">{device.os || "OS не указан"} · agent {device.agent_version || "unknown"}</span>
                      </span>
                    </label>
                    <button
                      aria-label={`Open requester device detail ${device.device_id}`}
                      className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
                      disabled={deviceDetailLoading}
                      onClick={() => void openDeviceDetail(device.device_id)}
                      type="button"
                    >
                      {deviceDetailLoading && selectedDeviceId === device.device_id ? "Загружаем..." : "Подробнее"}
                    </button>
                  </div>
                ))
                ) : (
                  <p className="text-sm text-slate-500">
                    <span className="block">Зарегистрированных устройств пока нет.</span>
                    <span className="block">Можно создать общее обращение без привязки к устройству.</span>
                  </p>
                )}
            </div>
            {deviceDetailError ? <p className="mt-3 text-sm text-rose-700">{deviceDetailError}</p> : null}
            {selectedDeviceDetail ? (
              <div className="mt-4 rounded-panel border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
                <p className="font-semibold text-slate-950">Сведения об устройстве</p>
                <dl className="mt-3 grid gap-2">
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Имя</dt>
                    <dd className="break-words font-semibold text-slate-900">{deviceLabel(selectedDeviceDetail.device)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Система</dt>
                    <dd className="break-words">{selectedDeviceDetail.device.os || "OS не указан"} · agent {selectedDeviceDetail.device.agent_version || "unknown"}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Связь</dt>
                    <dd>{relationshipLabel(selectedDeviceDetail.device.relationship_type)} · {selectedDeviceDetail.device.binding_status || "status unknown"}</dd>
                  </div>
                  {selectedDeviceDetail.device.asset_name ? (
                    <div>
                      <dt className="text-xs font-semibold uppercase text-slate-500">Актив</dt>
                      <dd className="break-words">{selectedDeviceDetail.device.asset_name}</dd>
                    </div>
                  ) : null}
                  <div>
                    <dt className="text-xs font-semibold uppercase text-slate-500">Активность</dt>
                    <dd>{selectedDeviceDetail.device.online ? "online" : "offline"} · Открытые обращения: {selectedDeviceDetail.device.open_ticket_count ?? 0}</dd>
                  </div>
                </dl>
                {selectedDeviceDetail.recent_tickets?.length ? (
                  <div className="mt-3 border-t border-slate-200 pt-3">
                    <p className="text-xs font-semibold uppercase text-slate-500">Последние обращения</p>
                    <div className="mt-2 grid gap-2">
                      {selectedDeviceDetail.recent_tickets.map((ticket) => (
                        <button
                          className="rounded-panel border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-700 hover:border-brand-300"
                          key={ticket.ticket_id}
                          onClick={() => void openTicket(ticket.ticket_id)}
                          type="button"
                        >
                          <span className="block break-words font-semibold text-slate-900">{ticket.title || ticket.ticket_code || ticket.ticket_id}</span>
                          <span className="block text-slate-500">{ticketStatus(ticket)}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>

          <form className="support-workspace__panel space-y-3" onSubmit={(event) => void handleClaimPublicTicket(event)}>
            <div className="support-workspace__panel-head">
              <div>
                <p className="workspace-boot__eyebrow">Публичный доступ</p>
                <h2 className="text-lg font-semibold text-slate-950">Привязать обращение</h2>
              </div>
            </div>
            <label className="block text-sm font-semibold text-slate-700">
              Номер заявки
              <input
                aria-label="Public ticket id to claim"
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setClaimTicketId(event.currentTarget.value)}
                value={claimTicketId}
              />
            </label>
            <label className="block text-sm font-semibold text-slate-700">
              Код доступа
              <input
                aria-label="Public ticket access code to claim"
                className="mt-1 w-full rounded-panel border border-slate-200 px-3 py-2 font-normal"
                onChange={(event) => setClaimCode(event.currentTarget.value)}
                value={claimCode}
              />
            </label>
            {claimNotice ? <p className="text-sm text-emerald-700">{claimNotice}</p> : null}
            <button
              aria-label="Claim public requester ticket"
              className="inline-flex w-full items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 disabled:cursor-not-allowed disabled:bg-slate-100"
              disabled={claimSubmitting || !claimTicketId.trim() || !claimCode.trim()}
              type="submit"
            >
              <Link2 className="h-4 w-4" />
              {claimSubmitting ? "Привязываем..." : "Привязать"}
            </button>
          </form>

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
                disabled={previewSubmitting || !canCreateForCurrentScope || !description.trim() || !selectedOffering}
                onClick={() => void handlePreview()}
                type="button"
              >
                {previewSubmitting ? "Проверяем..." : "Проверить заявку"}
              </button>
              <button
                aria-label="Create requester ticket"
                className="inline-flex w-full items-center justify-center gap-2 rounded-panel bg-brand-700 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                disabled={submitting || !canCreateForCurrentScope || !description.trim() || Boolean(selectedOffering && !previewIsFresh)}
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
