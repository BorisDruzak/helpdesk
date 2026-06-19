import type { LucideIcon } from "lucide-react";
import { CheckCircle2, Clock3, MonitorUp, MousePointer2, ShieldAlert, ShieldCheck, Wrench, X } from "lucide-react";
import { useRef, useState } from "react";

import { formatHumanIdentifier, formatRussianDateTime } from "../../components/ui-page";
import { cn } from "../../shared/ui/cn";
import type { RequesterConsent } from "./types";

export type RequesterConsentDecision = "approved" | "denied";

export type RequesterConsentListProps = {
  className?: string;
  consents: RequesterConsent[];
  disabled?: boolean;
  heading?: string;
  onDecision: (consent: RequesterConsent, decision: RequesterConsentDecision) => void | Promise<void>;
};

type ConsentProfile = {
  Icon: LucideIcon;
  action: string;
  scope: string;
  toneClass: string;
};

const UUID_IN_TEXT_PATTERN = /\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b/gi;
const TECHNICAL_TOKEN_PATTERN = /\b(?:consent|subject|session|binding|person|actor|device|remote-assist|diag|operation|op)-[a-z0-9][a-z0-9_-]{2,}\b/gi;

function normalized(value: unknown): string {
  return String(value ?? "").trim().toLowerCase();
}

function payloadString(consent: RequesterConsent, key: string): string {
  const value = consent.requested_action_payload_redacted?.[key];
  return typeof value === "string" ? value : "";
}

function consentProfile(consent: RequesterConsent): ConsentProfile {
  const subjectType = normalized(consent.subject_type);
  const riskLevel = normalized(consent.risk_level);
  const mode = normalized(payloadString(consent, "mode"));

  if (riskLevel.includes("admin") || mode.includes("admin") || mode.includes("elevated")) {
    return {
      Icon: ShieldAlert,
      action: "Административный доступ",
      scope: "Действия с повышенными правами в рамках обращения.",
      toneClass: "border-rose-200 bg-rose-50 text-rose-800",
    };
  }

  if (riskLevel.includes("remote_control") || mode.includes("control")) {
    return {
      Icon: MousePointer2,
      action: "Удаленное управление",
      scope: "Временное управление рабочим местом в рамках обращения.",
      toneClass: "border-amber-200 bg-amber-50 text-amber-800",
    };
  }

  if (riskLevel.includes("remote_view") || mode.includes("view") || mode.includes("screen")) {
    return {
      Icon: MonitorUp,
      action: "Просмотр экрана",
      scope: "Временный просмотр экрана без управления устройством.",
      toneClass: "border-sky-200 bg-sky-50 text-sky-800",
    };
  }

  if (
    subjectType === "operation" ||
    subjectType === "tool_run" ||
    subjectType.includes("diagnostic") ||
    riskLevel.includes("diagnostic") ||
    riskLevel.includes("safe_read") ||
    riskLevel.includes("sensitive_read")
  ) {
    return {
      Icon: Wrench,
      action: "Диагностика",
      scope: "Результаты проверки по обращению без управления устройством.",
      toneClass: "border-emerald-200 bg-emerald-50 text-emerald-800",
    };
  }

  if (subjectType === "remote_assist") {
    return {
      Icon: MonitorUp,
      action: "Просмотр экрана",
      scope: "Временный просмотр экрана без управления устройством.",
      toneClass: "border-sky-200 bg-sky-50 text-sky-800",
    };
  }

  return {
    Icon: ShieldCheck,
    action: "Запрос согласия",
    scope: "Действие будет выполнено только после вашего решения.",
    toneClass: "border-slate-200 bg-slate-50 text-slate-700",
  };
}

function safeText(value: unknown): string {
  return String(value ?? "")
    .trim()
    .replace(UUID_IN_TEXT_PATTERN, "идентификатор скрыт")
    .replace(TECHNICAL_TOKEN_PATTERN, "идентификатор скрыт");
}

function titleForConsent(consent: RequesterConsent, profile: ConsentProfile): string {
  return safeText(consent.title) || profile.action;
}

function descriptionForConsent(consent: RequesterConsent): string | null {
  const text = safeText(consent.description);
  return text || null;
}

function reasonForConsent(consent: RequesterConsent): string | null {
  const text =
    safeText(consent.reason) ||
    safeText(consent.requested_action_payload_redacted?.reason) ||
    safeText(consent.risk_explanation);
  return text || null;
}

function durationForConsent(consent: RequesterConsent): string | null {
  const value = consent.requested_action_payload_redacted?.duration_minutes;
  const minutes = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return null;
  }
  return `${minutes} мин`;
}

function requestedByLabel(role?: string | null): string {
  const key = normalized(role);
  if (key === "admin") {
    return "администратор";
  }
  if (key === "support" || key === "operator" || key === "user") {
    return "специалист поддержки";
  }
  if (key === "system") {
    return "система";
  }
  return "специалист";
}

function requestLabel(consent: RequesterConsent): string {
  return consent.ticket_id ? formatHumanIdentifier(consent.ticket_id, { uuidPrefix: "Обращение" }) : "обращение не указано";
}

export function RequesterConsentList({
  className,
  consents,
  disabled = false,
  heading = "Ожидают вашего решения",
  onDecision,
}: RequesterConsentListProps) {
  const pendingIdsRef = useRef<Set<string>>(new Set());
  const [pendingIds, setPendingIds] = useState<Set<string>>(() => new Set());

  if (!consents.length) {
    return null;
  }

  function setPending(consentId: string, value: boolean) {
    if (value) {
      pendingIdsRef.current.add(consentId);
    } else {
      pendingIdsRef.current.delete(consentId);
    }
    setPendingIds(new Set(pendingIdsRef.current));
  }

  async function decide(consent: RequesterConsent, decision: RequesterConsentDecision) {
    if (disabled || pendingIdsRef.current.has(consent.consent_id)) {
      return;
    }
    setPending(consent.consent_id, true);
    try {
      await onDecision(consent, decision);
    } finally {
      setPending(consent.consent_id, false);
    }
  }

  return (
    <section aria-label="Ожидающие согласия заявителя" className={cn("rounded-panel border border-amber-200 bg-amber-50 p-4", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase text-amber-700">Согласие пользователя</p>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">{heading}</h2>
        </div>
        <span className="rounded-panel bg-white px-3 py-1 text-sm font-semibold text-amber-800">{consents.length}</span>
      </div>

      <div className="mt-4 grid gap-3">
        {consents.map((consent, index) => {
          const profile = consentProfile(consent);
          const title = titleForConsent(consent, profile);
          const description = descriptionForConsent(consent);
          const reason = reasonForConsent(consent);
          const duration = durationForConsent(consent);
          const expiresAt = consent.expires_at ? formatRussianDateTime(consent.expires_at) : null;
          const busy = disabled || pendingIds.has(consent.consent_id);
          const titleId = `requester-action-${index}-title`;
          const Icon = profile.Icon;

          return (
            <article aria-labelledby={titleId} className="rounded-panel border border-amber-200 bg-white px-4 py-3" key={consent.consent_id} role="article">
              <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0 space-y-3">
                  <div className="flex min-w-0 items-start gap-3">
                    <span aria-hidden="true" className={cn("inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-panel border", profile.toneClass)}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <div className="min-w-0">
                      <p className="text-xs font-semibold uppercase text-amber-700">{profile.action}</p>
                      <h3 className="mt-1 break-words text-base font-semibold text-slate-950" id={titleId}>
                        {title}
                      </h3>
                      {description ? <p className="mt-1 break-words text-sm leading-6 text-slate-700">{description}</p> : null}
                    </div>
                  </div>

                  <dl className="grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
                    <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2">
                      <dt className="text-xs font-semibold uppercase text-slate-500">Действие</dt>
                      <dd className="mt-1 font-semibold text-slate-900">{profile.action}</dd>
                    </div>
                    <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2">
                      <dt className="text-xs font-semibold uppercase text-slate-500">Доступ</dt>
                      <dd className="mt-1 text-slate-800">{profile.scope}</dd>
                    </div>
                    <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2">
                      <dt className="text-xs font-semibold uppercase text-slate-500">Обращение</dt>
                      <dd className="mt-1 font-semibold text-slate-900">{requestLabel(consent)}</dd>
                    </div>
                    <div className="rounded-panel border border-slate-200 bg-slate-50 px-3 py-2">
                      <dt className="text-xs font-semibold uppercase text-slate-500">Срок</dt>
                      <dd className="mt-1 flex items-center gap-1 text-slate-800">
                        <Clock3 aria-hidden="true" className="h-4 w-4" />
                        {expiresAt ? `До: ${expiresAt}` : "До решения"}
                        {duration ? `, до ${duration}` : ""}
                      </dd>
                    </div>
                  </dl>

                  <div className="flex flex-wrap gap-2 text-xs font-semibold text-slate-600">
                    <span className="rounded-panel bg-slate-100 px-2 py-1">Для: текущий заявитель</span>
                    <span className="rounded-panel bg-slate-100 px-2 py-1">Запросил: {requestedByLabel(consent.requested_by_role)}</span>
                    {reason ? <span className="rounded-panel bg-slate-100 px-2 py-1">Причина: {reason}</span> : null}
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
                  <button
                    aria-label="Отклонить запрос согласия"
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-panel border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
                    disabled={busy}
                    onClick={() => void decide(consent, "denied")}
                    type="button"
                  >
                    <X aria-hidden="true" className="h-4 w-4" />
                    Отклонить
                  </button>
                  <button
                    aria-label="Разрешить запрос согласия"
                    className="inline-flex min-h-10 items-center justify-center gap-2 rounded-panel bg-emerald-700 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-slate-300"
                    disabled={busy}
                    onClick={() => void decide(consent, "approved")}
                    type="button"
                  >
                    <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
                    Разрешить
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
