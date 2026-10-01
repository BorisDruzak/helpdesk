import {
  useEffect,
  useState,
} from "react";
import {
  Badge,
} from "../../../components/ui/badge";
import {
  Button,
} from "../../../components/ui/button";
import {
  type SupportTicketEvidenceCandidatesPayload,
  type SupportTicketPassportEvidenceCreatePayload,
  type SupportTicketPassportPayload,
  type SupportTicketPassportSectionPatchPayload,
} from "../../../features/queues/api";
import {
  formatDateTime,
  PASSPORT_SECTION_LABELS,
  asPassportText,
  formatPassportRequirementSource,
  formatPassportStaleReason,
  passportSourceCandidates,
  passportEvidenceSourceLabel,
  passportCandidateSourceLabel,
} from '../detail-formatting';
export function TicketPassportPanel({
  candidates,
  disabledReason = null,
  isCreatingEvidence = false,
  isGenerating,
  isLinkingCandidate = false,
  isPatchingSections = false,
  onCreateEvidence,
  onGenerate,
  onLinkCandidate,
  onPatchSections,
  onPrint,
  onRefresh,
  payload,
}: {
  candidates?: SupportTicketEvidenceCandidatesPayload;
  disabledReason?: string | null;
  isCreatingEvidence?: boolean;
  isGenerating: boolean;
  isLinkingCandidate?: boolean;
  isPatchingSections?: boolean;
  onCreateEvidence?: (evidence: SupportTicketPassportEvidenceCreatePayload) => void;
  onGenerate: () => void;
  onLinkCandidate?: (link: { source_kind: string; source_id: string; required_fact?: string | null; visibility?: string }) => void;
  onPatchSections?: (patch: SupportTicketPassportSectionPatchPayload) => void;
  onPrint: () => void;
  onRefresh: () => void;
  payload?: SupportTicketPassportPayload;
}) {
  const passportForDraft = payload?.passport ?? null;
  const [manualEvidenceDraft, setManualEvidenceDraft] = useState({
    evidence_type: "manual_note",
    required_fact: "evidence",
    title: "",
    summary: "",
    visibility: "internal",
    export_visibility: "internal",
  });
  const [sectionDraft, setSectionDraft] = useState<Required<SupportTicketPassportSectionPatchPayload>>({
    operator_check_summary: "",
    changes_made_summary: "",
    repeat_guidance: "",
    user_result_summary: "",
    internal_result_summary: "",
  });

  useEffect(() => {
    if (!passportForDraft) {
      return;
    }
    setSectionDraft({
      operator_check_summary: passportForDraft.sections.operator_checks || "",
      changes_made_summary: passportForDraft.sections.changes_made || "",
      repeat_guidance: passportForDraft.sections.repeat_guidance || "",
      user_result_summary: passportForDraft.sections.user_result || "",
      internal_result_summary: passportForDraft.sections.internal_result || "",
    });
  }, [passportForDraft?.passport_id, passportForDraft?.version]);

  if (!payload || !payload.passport) {
    return (
      <div className="rounded-[1.1rem] border border-dashed border-border bg-surface-subtle px-5 py-10 text-center">
        <p className="font-semibold text-slate-950">Паспорт решения ещё не собран</p>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-500">
          Система соберёт черновик из полей заявки, истории, операций, доказательств и итогов решения.
        </p>
        {disabledReason ? (
          <p className="mx-auto mt-4 max-w-xl rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            {disabledReason}
          </p>
        ) : null}
        <Button className="mt-5" disabled={Boolean(disabledReason) || isGenerating} onClick={onGenerate}>
          {isGenerating ? "Собираем..." : "Собрать паспорт"}
        </Button>
      </div>
    );
  }

  const passport = payload.passport;
  const requirements = payload.requirements;
  const missingFacts = requirements?.missing_facts ?? [];
  const hiddenExportSections = requirements?.export_preview?.hidden_sections ?? [];
  const visibleExportSections = requirements?.export_preview?.visible_sections ?? [];
  const staleReasons = Array.isArray(passport.source_payload?.stale_reasons)
    ? passport.source_payload.stale_reasons.map(String).filter(Boolean)
    : [];
  const currentSourceCounts =
    passport.source_payload?.current_source_counts && typeof passport.source_payload.current_source_counts === "object"
      ? (passport.source_payload.current_source_counts as Record<string, unknown>)
      : {};

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 rounded-[1.1rem] border border-border bg-white px-5 py-5 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-brand-700">Паспорт решения</p>
          <h2 className="mt-2 text-xl font-semibold text-slate-950">Версия {passport.version}</h2>
          <p className="mt-1 text-sm text-slate-500">
            Собран {formatDateTime(passport.generated_at)} • источник: {passport.summary_source}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button disabled={Boolean(disabledReason) || isGenerating} onClick={onRefresh} size="sm" variant="outline">
            Обновить по последним действиям
          </Button>
          <Button onClick={onPrint} size="sm" variant="outline">
            Печать / PDF
          </Button>
        </div>
      </div>

      {disabledReason ? (
        <p className="rounded-[0.8rem] border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {disabledReason}
        </p>
      ) : null}

      {passport.stale ? (
        <div className="rounded-[1rem] border border-amber-200 bg-amber-50 px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-amber-950">Паспорт устарел</p>
              <p className="mt-1 text-sm text-amber-800">
                После сборки появились новые источники. Обновите паспорт перед закрытием или экспортом.
              </p>
            </div>
            <Button disabled={Boolean(disabledReason) || isGenerating} onClick={onRefresh} size="sm">
              {isGenerating ? "Обновляем..." : "Обновить паспорт"}
            </Button>
          </div>
          {staleReasons.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {staleReasons.map((reason) => (
                <Badge key={reason} tone="warning">
                  {formatPassportStaleReason(reason)}
                </Badge>
              ))}
            </div>
          ) : null}
          {Object.keys(currentSourceCounts).length ? (
            <p className="mt-3 text-xs text-amber-800">
              Текущие источники:{" "}
              {Object.entries(currentSourceCounts)
                .map(([key, value]) => `${key}: ${String(value)}`)
                .join(", ")}
            </p>
          ) : null}
        </div>
      ) : null}

      {requirements ? (
        <div className="rounded-[1.1rem] border border-border bg-white px-5 py-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Требования паспорта</p>
              <p className="mt-2 text-sm text-slate-600">
                {requirements.require_official_passport ? "Официальный паспорт обязателен перед закрытием." : "Паспорт не блокирует закрытие."}
              </p>
            </div>
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-sm font-semibold text-amber-800">
              {requirements.blocking_missing_count} блокирующих факта
            </div>
          </div>
          {missingFacts.length ? (
            <div className="mt-4 grid gap-2 md:grid-cols-2">
              {missingFacts.map((fact) => {
                const sourceCandidates = passportSourceCandidates(fact);
                const recommendedActions = Array.isArray(fact.recommended_actions) ? fact.recommended_actions : [];
                return (
                  <div className="rounded-lg border border-amber-100 bg-amber-50/60 px-3 py-3" key={`${fact.required_fact}:${fact.source}`}>
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-950">{fact.requester_visible_label}</p>
                        <p className="mt-1 text-xs text-slate-600">{formatPassportRequirementSource(fact.source)}</p>
                      </div>
                      <Badge tone={fact.severity === "blocking" ? "warning" : "neutral"}>
                        {fact.severity === "blocking" ? "Блокирует закрытие" : "Проверить"}
                      </Badge>
                    </div>
                    {fact.current_value ? <p className="mt-2 text-xs text-slate-700">{fact.current_value}</p> : null}
                    {recommendedActions.length ? (
                      <ul className="mt-2 space-y-1 text-xs text-slate-700">
                        {recommendedActions.map((action) => (
                          <li key={action}>{action}</li>
                        ))}
                      </ul>
                    ) : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button disabled={Boolean(disabledReason) || isGenerating} onClick={onRefresh} size="sm" variant="outline">
                        Обновить паспорт
                      </Button>
                      {sourceCandidates.length ? <Badge tone="info">Кандидаты: {sourceCandidates.length}</Badge> : null}
                    </div>
                    {sourceCandidates.length ? (
                      <div className="mt-3 space-y-2">
                        {sourceCandidates.slice(0, 3).map((candidate, index) => {
                          const title = asPassportText(candidate.title) || asPassportText(candidate.candidate_id) || `Кандидат ${index + 1}`;
                          const summary = asPassportText(candidate.summary);
                          const sourceKind = asPassportText(candidate.source_kind);
                          return (
                            <div className="rounded-md border border-white/80 bg-white px-3 py-2 text-xs" key={`${title}:${index}`}>
                              <p className="font-semibold text-slate-900">{title}</p>
                              {summary ? <p className="mt-1 text-slate-600">{summary}</p> : null}
                              {sourceKind ? <p className="mt-1 text-slate-500">Тип источника: {sourceKind}</p> : null}
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-4 rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
              Все обязательные факты заполнены.
            </p>
          )}
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
            <p className="text-sm font-semibold text-slate-950">Экспорт</p>
            <p className="mt-1 text-xs text-slate-600">
              Видно: {visibleExportSections.length ? visibleExportSections.join(", ") : "все доступные разделы"}
            </p>
            <p className="mt-1 text-xs text-slate-600">
              Скрыто: {hiddenExportSections.length ? hiddenExportSections.join(", ") : "нет скрытых разделов"}
            </p>
          </div>
        </div>
      ) : null}

      <div className="rounded-[1.1rem] border border-border bg-white px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Доказательства паспорта</p>
            <p className="mt-2 text-sm text-slate-600">
              Принятые и проверяемые факты, которые подтверждают официальный итог.
            </p>
          </div>
          <Badge tone={payload.evidence.length ? "brand" : "neutral"}>{payload.evidence.length}</Badge>
        </div>
        {payload.evidence.length ? (
          <div className="mt-4 space-y-2">
            {payload.evidence.map((item) => (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3" key={item.id}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-950">{item.title}</p>
                    {item.summary ? <p className="mt-1 text-sm text-slate-600">{item.summary}</p> : null}
                    <p className="mt-1 text-xs text-slate-500">Источник: {passportEvidenceSourceLabel(item)}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="info">{item.evidence_type}</Badge>
                    <Badge tone={item.verification_status === "accepted" ? "success" : "neutral"}>
                      {item.verification_status || "unverified"}
                    </Badge>
                    <Badge tone={item.export_visibility === "public" ? "success" : "neutral"}>
                      {item.export_visibility || item.visibility}
                    </Badge>
                  </div>
                </div>
                <p className="mt-2 text-xs text-slate-500">
                  Факт: {item.required_fact || "не привязан"} • раздел: {item.section_key || "не указан"} • добавил:{" "}
                  {item.created_by || "неизвестно"}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
            Доказательства ещё не привязаны.
          </p>
        )}
      </div>

      <div className="rounded-[1.1rem] border border-border bg-white px-5 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Кандидаты доказательств</p>
            <p className="mt-2 text-sm text-slate-600">
              Источники из worklog, согласований, чата, операций и observer trace, которые можно привязать к паспорту.
            </p>
          </div>
          <Badge tone={candidates?.candidates.length ? "info" : "neutral"}>{candidates?.candidates.length ?? 0}</Badge>
        </div>
        {candidates?.candidates.length ? (
          <div className="mt-4 space-y-2">
            {candidates.candidates.slice(0, 8).map((candidate) => (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3" key={candidate.candidate_id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-slate-950">{candidate.title}</p>
                      {candidate.existing_evidence_id ? <Badge tone="success">Уже привязано</Badge> : null}
                    </div>
                    {candidate.summary ? <p className="mt-1 text-sm text-slate-600">{candidate.summary}</p> : null}
                    <p className="mt-1 text-xs text-slate-500">
                      {passportCandidateSourceLabel(candidate)} • {candidate.source_ref} • факт: {candidate.required_fact}
                    </p>
                  </div>
                  <Button
                    disabled={Boolean(disabledReason) || Boolean(candidate.existing_evidence_id) || isLinkingCandidate}
                    onClick={() =>
                      onLinkCandidate?.({
                        source_kind: candidate.source_kind,
                        source_id: candidate.source_id,
                        required_fact: candidate.required_fact,
                        visibility: candidate.visibility || "internal",
                      })
                    }
                    size="sm"
                    variant="outline"
                  >
                    {isLinkingCandidate ? "Привязываем..." : "Привязать"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
            Кандидаты не найдены. Можно добавить ручное доказательство ниже.
          </p>
        )}
      </div>

      <form
        className="rounded-[1.1rem] border border-border bg-white px-5 py-5"
        onSubmit={(event) => {
          event.preventDefault();
          const title = manualEvidenceDraft.title.trim();
          if (!title || !onCreateEvidence) {
            return;
          }
          onCreateEvidence({
            evidence_type: manualEvidenceDraft.evidence_type,
            required_fact: manualEvidenceDraft.required_fact,
            section_key: manualEvidenceDraft.required_fact,
            title,
            summary: manualEvidenceDraft.summary.trim() || null,
            visibility: manualEvidenceDraft.visibility,
            verification_status: "accepted",
            export_visibility: manualEvidenceDraft.export_visibility,
          });
          setManualEvidenceDraft((draft) => ({ ...draft, title: "", summary: "" }));
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Ручное доказательство</p>
            <p className="mt-2 text-sm text-slate-600">
              Для фактов, которые оператор проверил вне автоматической диагностики.
            </p>
          </div>
          <Button disabled={Boolean(disabledReason) || isCreatingEvidence || !manualEvidenceDraft.title.trim()} size="sm" type="submit">
            {isCreatingEvidence ? "Добавляем..." : "Добавить доказательство"}
          </Button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Название доказательства
            <input
              className="mt-1 h-10 w-full rounded-[0.75rem] border border-border bg-white px-3 text-sm outline-none transition-colors focus:border-brand-400"
              onChange={(event) => setManualEvidenceDraft((draft) => ({ ...draft, title: event.target.value }))}
              value={manualEvidenceDraft.title}
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Факт паспорта
            <select
              className="mt-1 h-10 w-full rounded-[0.75rem] border border-border bg-white px-3 text-sm outline-none transition-colors focus:border-brand-400"
              onChange={(event) => setManualEvidenceDraft((draft) => ({ ...draft, required_fact: event.target.value }))}
              value={manualEvidenceDraft.required_fact}
            >
              <option value="evidence">Доказательство для закрытия</option>
              <option value="operator_checks">Проверка оператора</option>
              <option value="changes_made">Изменение или исправление</option>
              <option value="user_result">Итог для пользователя</option>
              <option value="internal_result">Внутренний итог</option>
            </select>
          </label>
          <label className="text-sm font-medium text-slate-700 md:col-span-2">
            Краткое описание
            <textarea
              className="mt-1 min-h-20 w-full rounded-[0.75rem] border border-border bg-white px-3 py-2 text-sm outline-none transition-colors focus:border-brand-400"
              onChange={(event) => setManualEvidenceDraft((draft) => ({ ...draft, summary: event.target.value }))}
              value={manualEvidenceDraft.summary}
            />
          </label>
        </div>
      </form>

      <form
        className="rounded-[1.1rem] border border-border bg-white px-5 py-5"
        onSubmit={(event) => {
          event.preventDefault();
          onPatchSections?.(sectionDraft);
        }}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Редактируемые разделы</p>
            <p className="mt-2 text-sm text-slate-600">
              Итоги и operator-check поля сохраняются в текущую версию паспорта.
            </p>
          </div>
          <Button disabled={Boolean(disabledReason) || isPatchingSections} size="sm" type="submit" variant="outline">
            {isPatchingSections ? "Сохраняем..." : "Сохранить разделы"}
          </Button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {[
            ["operator_check_summary", "Что проверил оператор"],
            ["changes_made_summary", "Что изменили"],
            ["user_result_summary", "Итог для пользователя"],
            ["internal_result_summary", "Внутренний тех. итог"],
            ["repeat_guidance", "Что делать при повторе"],
          ].map(([key, label]) => (
            <label className="text-sm font-medium text-slate-700" key={key}>
              Редактировать: {label}
              <textarea
                aria-label={label}
                className="mt-1 min-h-24 w-full rounded-[0.75rem] border border-border bg-white px-3 py-2 text-sm outline-none transition-colors focus:border-brand-400"
                onChange={(event) => setSectionDraft((draft) => ({ ...draft, [key]: event.target.value }))}
                value={String(sectionDraft[key as keyof typeof sectionDraft] ?? "")}
              />
            </label>
          ))}
        </div>
      </form>

      <div className="grid gap-4 md:grid-cols-2">
        {PASSPORT_SECTION_LABELS.map(([key, label]) => (
          <div key={key} className="rounded-[1.1rem] border border-border bg-white px-5 py-5">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">{label}</p>
            <p className="mt-3 whitespace-pre-line text-sm leading-7 text-slate-700">
              {passport.sections[key] || "Нет данных"}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Доказательства</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{payload.evidence.length}</p>
        </div>
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Действия</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{payload.actions.length}</p>
        </div>
        <div className="rounded-[1.1rem] bg-surface-subtle px-4 py-4">
          <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Согласования</p>
          <p className="mt-2 text-lg font-semibold text-slate-950">{payload.approvals.length}</p>
        </div>
      </div>
    </div>
  );
}