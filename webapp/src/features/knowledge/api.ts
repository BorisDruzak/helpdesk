export type KnowledgeSpace = {
  space_id: string;
  code: string;
  title: string;
  description?: string | null;
  visibility: string;
  lifecycle_status: string;
  owner_actor_id?: string | null;
  default_reviewer_actor_id?: string | null;
  allow_publication?: boolean;
  allow_ingestion?: boolean;
  allow_rag?: boolean;
};

export type KnowledgeItemVersion = {
  version_id: string;
  item_id: string;
  version_number: number;
  title: string;
  summary?: string | null;
  body_format: string;
  body?: string | null;
  created_at?: string | null;
  published_at?: string | null;
};

export type KnowledgeItem = {
  item_id: string;
  space_id: string;
  slug: string;
  item_type: string;
  type: string;
  title: string;
  summary?: string | null;
  status: string;
  visibility: string;
  owner_actor_id?: string | null;
  reviewer_actor_id?: string | null;
  current_version_id?: string | null;
  current_version?: KnowledgeItemVersion;
  tags?: string[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type KnowledgeMetricsSummary = {
  deflection?: {
    deflected_count?: number;
    ticket_created_after_view_count?: number;
    deflection_rate?: number;
  };
  helpfulness?: {
    helpful_count?: number;
    not_helpful_count?: number;
    helpfulness_rate?: number;
  };
  totals?: {
    suggested_count?: number;
    viewed_count?: number;
    feedback_count?: number;
  };
  events_by_type?: Record<string, number>;
  deflection_events?: number;
  helpful_events?: number;
  not_helpful_events?: number;
  ticket_created_after_view_events?: number;
  deflection_rate?: number;
};

export type KnowledgeContentPack = {
  pack_id: string;
  code: string;
  title: string;
  version: number;
  description?: string | null;
  installed_at?: string | null;
  installed_by?: string | null;
  source_hash?: string | null;
  status: string;
  metadata?: Record<string, unknown>;
};

export type KnowledgeContentPackApplyResult = {
  status: string;
  source_hash: string;
  dry_run?: boolean;
  items: Array<{
    item_slug: string;
    install_status?: string;
    status?: string;
    item_id?: string | null;
    version_id?: string | null;
    reason?: string | null;
    error?: string | null;
  }>;
  summary?: Record<string, number>;
};

export type KnowledgeTemplate = {
  type: string;
  title: string;
  sections: string[];
};

export type KnowledgeReviewQueue = {
  count: number;
  items: Array<
    KnowledgeItem & {
      reason: string;
      review_due_at?: string | null;
      task_id?: string;
      task_type?: string;
      severity?: string;
      suggested_action?: string | null;
    }
  >;
};

export type KnowledgeQualitySummary = {
  average_quality_score: number;
  items: Array<
    KnowledgeItem & {
      quality_score: number;
      issues: string[];
      feedback?: Record<string, number>;
    }
  >;
};

export type KnowledgeGapSummary = {
  count: number;
  gaps: Array<{
    finding_id?: string;
    gap_type: string;
    service_code: string;
    offering_code: string;
    service_title?: string | null;
    offering_title?: string | null;
    ticket_count: number;
    ticket_created_after_view_count: number;
    not_helpful_count: number;
    severity: string;
  }>;
};

export type KnowledgeReviewTask = {
  task_id: string;
  item_id: string;
  version_id?: string | null;
  task_type: string;
  severity: string;
  status: string;
  assigned_to_actor_id?: string | null;
  owner_actor_id?: string | null;
  due_at?: string | null;
  source_kind?: string | null;
  source_ref?: string | null;
  reason: string;
  suggested_action?: string | null;
  item?: KnowledgeItem;
};

export type KnowledgeGapFinding = {
  finding_id: string;
  service_code?: string | null;
  offering_code?: string | null;
  request_template_key?: string | null;
  gap_type: string;
  severity: string;
  status: string;
  evidence?: Record<string, unknown>;
  suggested_action?: string | null;
};

export type KnowledgeRolloutPolicy = {
  policy_id: string;
  scope_type?: string;
  service_code?: string | null;
  offering_code?: string | null;
  request_template_key?: string | null;
  surface: string;
  enabled: boolean;
  rollout_percent: number;
  reason?: string | null;
  show_before_form?: boolean;
  show_after_form?: boolean;
  require_suggestions_before_submit?: boolean;
  allow_skip?: boolean;
  urgency_bypass?: boolean;
  impact_bypass?: boolean;
  min_suggestions?: number;
  max_suggestions?: number;
  deflection_prompt_enabled?: boolean;
  feedback_required_on_article_view?: boolean;
  show_known_errors?: boolean;
  show_quality_badge?: boolean;
  show_review_freshness?: boolean;
  no_suggestions_behavior?: string;
  api_unavailable_behavior?: string;
  bypass_applied?: boolean;
  bypass_reason?: string | null;
  rollout_bucket?: number;
  updated_at?: string | null;
  updated_by?: string | null;
};

export type KnowledgeAiProvider = {
  provider_id: string;
  code: string;
  title: string;
  provider_type: string;
  base_url?: string | null;
  auth_type?: string | null;
  data_policy?: string | null;
  enabled: boolean;
  health_status?: string | null;
  last_health_check_at?: string | null;
  last_error_redacted?: string | null;
  api_key_configured?: boolean;
  api_key_secret_ref_masked?: string | null;
  api_key_secret_ref?: string | null;
};

export type KnowledgeAiModelProfile = {
  profile_id: string;
  provider_id?: string | null;
  code?: string | null;
  title: string;
  task_type: string;
  model_name: string;
  timeout_ms?: number | null;
  max_retries?: number | null;
  temperature?: number | null;
  enabled: boolean;
  is_default?: boolean;
};

export type KnowledgeAiPolicy = {
  policy_id: string;
  scope_type: string;
  task_type?: string | null;
  enabled: boolean;
  ai_allowed: boolean;
  embedding_allowed?: boolean;
  rerank_allowed?: boolean;
  answer_allowed?: boolean;
  rewrite_allowed?: boolean;
  auto_markup_allowed?: boolean;
  redact_before_send?: boolean;
  allow_cloud_for_requester_safe?: boolean;
  require_local_for_security_restricted?: boolean;
};

export type KnowledgeAiAuditRow = {
  audit_id: string;
  provider_id?: string | null;
  model_profile_id?: string | null;
  task_type?: string | null;
  status?: string | null;
  error_code?: string | null;
  error_message_redacted?: string | null;
  created_at?: string | null;
};

export type KnowledgeAiHealthResult = {
  provider_id: string;
  status: string;
  error_code?: string | null;
};

export type KnowledgeSearchSettings = {
  settings_id: string;
  search_mode: string;
  effective_mode: string;
  fallback_mode?: string | null;
  ai_enabled: boolean;
  enabled?: boolean;
  keyword_enabled: boolean;
  full_text_enabled: boolean;
  vector_enabled: boolean;
  rerank_enabled: boolean;
  ai_query_rewrite_enabled: boolean;
  rag_answer_enabled: boolean;
  keyword_weight?: number | null;
  full_text_weight?: number | null;
  vector_weight?: number | null;
  max_results: number;
  snippet_length: number;
  metadata_json?: Record<string, unknown>;
  updated_at?: string | null;
  updated_by?: string | null;
};

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.details ?? payload?.error ?? fallbackMessage);
  }
  return payload as T;
}

export async function fetchKnowledgeSpaces(): Promise<KnowledgeSpace[]> {
  const response = await fetch("/api/web/knowledge/spaces", { credentials: "same-origin" });
  const payload = await readJson<{ spaces: KnowledgeSpace[] }>(response, "Не удалось загрузить пространства знаний");
  return payload.spaces ?? [];
}

export async function saveKnowledgeSpace(payload: Partial<KnowledgeSpace> & { code: string; title: string }) {
  const response = await fetch("/api/web/knowledge/spaces", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ space: KnowledgeSpace }>(response, "Не удалось сохранить пространство знаний");
}

export async function fetchKnowledgeItems(): Promise<KnowledgeItem[]> {
  const response = await fetch("/api/web/knowledge/items", { credentials: "same-origin" });
  const payload = await readJson<{ items: KnowledgeItem[] }>(response, "Не удалось загрузить знания");
  return payload.items ?? [];
}

export async function createKnowledgeItem(payload: Record<string, unknown>) {
  const response = await fetch("/api/web/knowledge/items", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ item: KnowledgeItem }>(response, "Не удалось создать черновик знания");
}

export async function createKnowledgeVersion(itemIdOrSlug: string, payload: Record<string, unknown>) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/versions`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ version: KnowledgeItemVersion }>(response, "Не удалось создать версию знания");
}

export async function fetchKnowledgeItemVersions(itemIdOrSlug: string): Promise<KnowledgeItemVersion[]> {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/versions`, {
    credentials: "same-origin",
  });
  const payload = await readJson<{ versions: KnowledgeItemVersion[] }>(response, "Не удалось загрузить версии знания");
  return payload.versions ?? [];
}

export async function publishKnowledgeItem(
  itemIdOrSlug: string,
  versionId: string,
  options?: { acknowledge_stale_passport?: boolean; review_note?: string | null },
) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/publish`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version_id: versionId, ...(options ?? {}) }),
  });
  return readJson<{ item: KnowledgeItem }>(response, "Не удалось опубликовать знание");
}

export async function fetchKnowledgeMetricsSummary(): Promise<KnowledgeMetricsSummary> {
  const response = await fetch("/api/web/knowledge/metrics/summary", { credentials: "same-origin" });
  const payload = await readJson<{ summary: KnowledgeMetricsSummary }>(response, "Не удалось загрузить метрики знаний");
  return payload.summary;
}

export async function fetchKnowledgeContentPacks(): Promise<KnowledgeContentPack[]> {
  const response = await fetch("/api/web/knowledge/content-packs", { credentials: "same-origin" });
  const payload = await readJson<{ packs: KnowledgeContentPack[] }>(response, "Не удалось загрузить content packs");
  return payload.packs ?? [];
}

export async function applyKnowledgeContentPack(payload: { pack: Record<string, unknown>; dry_run?: boolean; force?: boolean }) {
  const response = await fetch("/api/web/knowledge/content-packs/apply", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ result: KnowledgeContentPackApplyResult }>(response, "Не удалось применить content pack");
}

export async function retireKnowledgeContentPack(packCode: string) {
  const response = await fetch(`/api/web/knowledge/content-packs/${encodeURIComponent(packCode)}/retire`, {
    method: "POST",
    credentials: "same-origin",
  });
  return readJson<{ result: Record<string, unknown> }>(response, "Не удалось retire content pack");
}

export async function fetchKnowledgeTemplates(): Promise<KnowledgeTemplate[]> {
  const response = await fetch("/api/web/knowledge/templates", { credentials: "same-origin" });
  const payload = await readJson<{ templates: KnowledgeTemplate[] }>(response, "Не удалось загрузить шаблоны знаний");
  return payload.templates ?? [];
}

export async function fetchKnowledgeReviewQueue(): Promise<KnowledgeReviewQueue> {
  const response = await fetch("/api/web/knowledge/review/tasks", { credentials: "same-origin" });
  const payload = await readJson<{ review_queue: KnowledgeReviewQueue }>(response, "Не удалось загрузить review queue");
  if (payload.review_queue) {
    return payload.review_queue;
  }
  const tasks = (payload as { tasks?: KnowledgeReviewTask[]; count?: number }).tasks ?? [];
  return {
    count: (payload as { count?: number }).count ?? tasks.length,
    items: tasks.map((task) => ({
      ...(task.item ?? {
        item_id: task.item_id,
        space_id: "",
        slug: task.source_ref ?? task.item_id,
        item_type: "article",
        type: "article",
        title: task.reason,
        status: "needs_review",
        visibility: "support_internal",
      }),
      reason: task.task_type,
      review_due_at: task.due_at,
      task_id: task.task_id,
      task_type: task.task_type,
      severity: task.severity,
      suggested_action: task.suggested_action,
    })),
  };
}

export async function submitKnowledgeReviewAction(itemIdOrSlug: string, payload: { action: string; note?: string | null }) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/review-action`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ result: { item: KnowledgeItem; event: Record<string, unknown> } }>(response, "Не удалось выполнить review action");
}

export async function submitKnowledgeReviewTaskAction(
  taskId: string,
  payload: { action: "assign" | "start" | "complete" | "dismiss"; note?: string | null; assigned_to_actor_id?: string | null },
) {
  const response = await fetch(`/api/web/knowledge/review/tasks/${encodeURIComponent(taskId)}/${encodeURIComponent(payload.action)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ task: KnowledgeReviewTask }>(response, "Failed to update knowledge review task");
}

export async function fetchKnowledgeQuality(): Promise<KnowledgeQualitySummary> {
  const response = await fetch("/api/web/knowledge/quality", { credentials: "same-origin" });
  const payload = await readJson<{ quality: KnowledgeQualitySummary }>(response, "Не удалось загрузить quality score");
  return payload.quality;
}

export async function fetchKnowledgeGaps(): Promise<KnowledgeGapSummary> {
  const response = await fetch("/api/web/knowledge/gap-findings", { credentials: "same-origin" });
  const payload = await readJson<{ gaps: KnowledgeGapSummary }>(response, "Не удалось загрузить knowledge gaps");
  if (payload.gaps) {
    return payload.gaps;
  }
  const findings = (payload as { findings?: KnowledgeGapFinding[]; count?: number }).findings ?? [];
  return {
    count: (payload as { count?: number }).count ?? findings.length,
    gaps: findings.map((finding) => {
      const evidence = finding.evidence ?? {};
      return {
        finding_id: finding.finding_id,
        gap_type: finding.gap_type,
        service_code: String(finding.service_code ?? ""),
        offering_code: String(finding.offering_code ?? ""),
        service_title: typeof evidence.service_title === "string" ? evidence.service_title : null,
        offering_title: typeof evidence.offering_title === "string" ? evidence.offering_title : null,
        ticket_count: Number(evidence.ticket_count ?? 0),
        ticket_created_after_view_count: Number(evidence.ticket_created_after_view_count ?? 0),
        not_helpful_count: Number(evidence.not_helpful_count ?? 0),
        severity: finding.severity,
      };
    }),
  };
}

export async function recomputeKnowledgeGaps() {
  const response = await fetch("/api/web/knowledge/gaps/recompute", {
    method: "POST",
    credentials: "same-origin",
  });
  return readJson<{ findings: KnowledgeGapFinding[]; count: number }>(response, "Failed to recompute knowledge gaps");
}

export async function submitKnowledgeGapAction(findingId: string, action: "accept" | "dismiss" | "create-draft", payload?: Record<string, unknown>) {
  const response = await fetch(`/api/web/knowledge/gaps/${encodeURIComponent(findingId)}/${encodeURIComponent(action)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  return readJson<Record<string, unknown>>(response, "Failed to update knowledge gap");
}

export async function fetchKnowledgeRolloutPolicies(): Promise<KnowledgeRolloutPolicy[]> {
  const response = await fetch("/api/web/knowledge/rollout-policies", { credentials: "same-origin" });
  const payload = await readJson<{ policies: KnowledgeRolloutPolicy[] }>(response, "Не удалось загрузить rollout policies");
  return payload.policies ?? [];
}

export async function saveKnowledgeRolloutPolicy(payload: Partial<KnowledgeRolloutPolicy>) {
  const response = await fetch("/api/web/knowledge/rollout-policies", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ policy: KnowledgeRolloutPolicy }>(response, "Не удалось сохранить rollout policy");
}

export async function fetchKnowledgeAiProviders(): Promise<KnowledgeAiProvider[]> {
  const response = await fetch("/api/web/knowledge/ai/providers", { credentials: "same-origin" });
  const payload = await readJson<{ providers: KnowledgeAiProvider[] }>(response, "Не удалось загрузить провайдеры AI");
  return payload.providers ?? [];
}

export async function saveKnowledgeAiProvider(payload: Partial<KnowledgeAiProvider> & { provider_id?: string }) {
  const providerId = payload.provider_id;
  const response = await fetch(
    providerId ? `/api/web/knowledge/ai/providers/${encodeURIComponent(providerId)}` : "/api/web/knowledge/ai/providers",
    {
      method: providerId ? "PATCH" : "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return readJson<{ provider: KnowledgeAiProvider; display_message?: string }>(response, "Не удалось сохранить провайдера AI");
}

export async function fetchKnowledgeAiModelProfiles(): Promise<KnowledgeAiModelProfile[]> {
  const response = await fetch("/api/web/knowledge/ai/model-profiles", { credentials: "same-origin" });
  const payload = await readJson<{ model_profiles: KnowledgeAiModelProfile[] }>(response, "Не удалось загрузить профили моделей");
  return payload.model_profiles ?? [];
}

export async function saveKnowledgeAiModelProfile(payload: Partial<KnowledgeAiModelProfile> & { profile_id?: string }) {
  const profileId = payload.profile_id;
  const response = await fetch(
    profileId ? `/api/web/knowledge/ai/model-profiles/${encodeURIComponent(profileId)}` : "/api/web/knowledge/ai/model-profiles",
    {
      method: profileId ? "PATCH" : "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  return readJson<{ model_profile: KnowledgeAiModelProfile; display_message?: string }>(response, "Не удалось сохранить профиль модели");
}

export async function fetchKnowledgeAiPolicies(): Promise<KnowledgeAiPolicy[]> {
  const response = await fetch("/api/web/knowledge/ai/policies", { credentials: "same-origin" });
  const payload = await readJson<{ policies: KnowledgeAiPolicy[] }>(response, "Не удалось загрузить политики AI");
  return payload.policies ?? [];
}

export async function saveKnowledgeAiPolicy(payload: Partial<KnowledgeAiPolicy>) {
  const response = await fetch("/api/web/knowledge/ai/policies", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ policy: KnowledgeAiPolicy; display_message?: string }>(response, "Не удалось сохранить политику AI");
}

export async function fetchKnowledgeAiAudit(): Promise<KnowledgeAiAuditRow[]> {
  const response = await fetch("/api/web/knowledge/ai/audit", { credentials: "same-origin" });
  const payload = await readJson<{ audit: KnowledgeAiAuditRow[]; display_message?: string }>(response, "Не удалось загрузить журнал AI");
  return payload.audit ?? [];
}

export async function checkKnowledgeAiProviderHealth(providerId: string, payload: { model_name?: string }) {
  const response = await fetch(`/api/web/knowledge/ai/providers/${encodeURIComponent(providerId)}/health-check`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ health: KnowledgeAiHealthResult; display_message?: string }>(response, "Не удалось проверить провайдера AI");
}

export async function fetchKnowledgeSearchSettings(): Promise<KnowledgeSearchSettings> {
  const response = await fetch("/api/web/knowledge/search-settings", { credentials: "same-origin" });
  const payload = await readJson<{ settings: KnowledgeSearchSettings; display_message?: string }>(
    response,
    "Не удалось загрузить настройки поиска",
  );
  return payload.settings;
}

export async function saveKnowledgeSearchSettings(payload: Partial<KnowledgeSearchSettings>) {
  const response = await fetch("/api/web/knowledge/search-settings", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ settings: KnowledgeSearchSettings; display_message?: string }>(
    response,
    "Не удалось сохранить настройки поиска",
  );
}
