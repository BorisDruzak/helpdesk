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

export type KnowledgeGraphNode = {
  node_id: string;
  node_type: string;
  stable_key: string;
  label: string;
  visibility: string;
  linked_item_id?: string | null;
  service_code?: string | null;
  offering_code?: string | null;
  status?: string | null;
};

export type KnowledgeGraphEdge = {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  relation_type: string;
  visibility: string;
  status?: string | null;
};

export type KnowledgeGraphNeighborhood = {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
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

export type KnowledgeSearchPreviewRequest = {
  query: string;
  actor_role?: string;
  surface?: string;
};

export type KnowledgeSearchPreviewResult = {
  status: string;
  display_message?: string;
  search_mode?: string;
  effective_mode?: string;
  ai_used?: boolean;
  results: Array<{
    item_id?: string;
    slug?: string;
    title: string;
    summary?: string | null;
    visibility?: string | null;
    score?: number | null;
  }>;
};

export type KnowledgeRetrievalResult = {
  status: string;
  display_message?: string;
  search_mode?: string;
  effective_mode?: string;
  fallback_mode?: string | null;
  ai_used?: boolean;
  settings?: Record<string, boolean>;
  results: Array<{
    item: KnowledgeItem;
    version?: { version_id: string; title?: string | null };
    chunk_id?: string | null;
    segment_id?: string | null;
    snippet?: string | null;
    score?: number;
    score_parts?: Record<string, number>;
    source_mode?: string[];
    fallback_mode?: string | null;
    citations?: Array<Record<string, unknown>>;
  }>;
};

export type KnowledgeAskResult = {
  status: string;
  answer?: string | null;
  answer_status: "answered" | "not_enough_evidence" | "ai_disabled" | "provider_unavailable" | "policy_blocked" | string;
  citations?: Array<{
    ref_id?: string;
    item_id?: string;
    version_id?: string;
    chunk_id?: string | null;
    segment_id?: string | null;
    title?: string | null;
    snippet?: string | null;
  }>;
  retrieval_results?: KnowledgeRetrievalResult["results"];
  confidence?: string | null;
  suggested_actions?: Array<{ type?: string; label?: string }>;
  observer_event_id?: string | null;
  audit_id?: string | null;
  ai_used?: boolean;
  search_mode?: string;
  effective_mode?: string;
  fallback_mode?: string | null;
  display_message?: string;
};

export type KnowledgePortalHome = {
  status?: string;
  display_message?: string;
  spaces: KnowledgeSpace[];
  featured_articles: KnowledgeItem[];
  recent_articles: KnowledgeItem[];
  popular_articles: KnowledgeItem[];
};

export type KnowledgePortalArticle = {
  status?: string;
  article: KnowledgeItem & {
    owner_actor_id?: string | null;
    review_due_at?: string | null;
    published_at?: string | null;
  };
  version: KnowledgeItemVersion;
  segments: Array<{
    segment_id: string;
    item_id?: string;
    version_id?: string;
    segment_index?: number;
    segment_type?: string;
    title: string;
    summary?: string | null;
    text?: string | null;
    heading_path?: string[];
    keywords?: string[];
    visibility?: string;
    status?: string;
  }>;
  related_articles: KnowledgeItem[];
};

export type KnowledgePortalEventResponse = {
  status: string;
  event: {
    event_id?: string;
    item_id?: string | null;
    version_id?: string | null;
    event_type: string;
    result?: string | null;
    metadata?: Record<string, unknown>;
  };
};

export type KnowledgePortalBookmarkResponse = {
  status: string;
  bookmark: {
    slug: string;
    bookmarked: boolean;
  };
  event?: KnowledgePortalEventResponse["event"];
};

export type KnowledgePortalCollection = {
  status?: string;
  collection_type: "space" | "tag" | string;
  collection_code: string;
  title: string;
  description?: string | null;
  space?: KnowledgeSpace;
  articles: KnowledgeItem[];
};

export type KnowledgeSegment = {
  segment_id: string;
  item_id: string;
  version_id: string;
  segment_index?: number;
  segment_type: string;
  title: string;
  summary?: string | null;
  text: string;
  start_offset?: number | null;
  end_offset?: number | null;
  heading_path?: string[];
  keywords?: string[];
  boost?: number | null;
  visibility: string;
  embedding_enabled?: boolean;
  full_text_enabled?: boolean;
  status: string;
  source?: string | null;
  content_hash?: string | null;
  metadata_json?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type KnowledgeIndexingStatus = {
  embeddings: Record<string, number>;
  jobs: Record<string, number>;
  vector_enabled: boolean;
  embedding_model?: string | null;
  model_profile_id?: string | null;
};

export type KnowledgeIndexJob = {
  job_id: string;
  scope_type: string;
  scope_ref?: string | null;
  model_profile_id?: string | null;
  status: string;
  requested_by?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  stats_json?: Record<string, number>;
  error_redacted?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type KnowledgeEmbeddingRecord = {
  embedding_id: string;
  chunk_id: string;
  segment_id?: string | null;
  item_id: string;
  version_id: string;
  model_profile_id?: string | null;
  embedding_model?: string | null;
  embedding_dimensions?: number | null;
  content_hash: string;
  embedding_input_hash?: string | null;
  visibility: string;
  status: string;
  indexed_at?: string | null;
  error_redacted?: string | null;
  metadata_json?: Record<string, unknown>;
};

export type KnowledgeSegmentationProfile = {
  profile_id: string;
  code: string;
  title: string;
  mode: string;
  split_by_headings?: boolean;
  split_by_paragraphs?: boolean;
  target_tokens?: number;
  max_tokens?: number;
  min_tokens?: number;
  overlap_tokens?: number;
  preserve_tables?: boolean;
  preserve_code_blocks?: boolean;
  default_segment_boost?: number | null;
  enabled?: boolean;
};

export type KnowledgeSegmentPayload = {
  version_id?: string;
  segment_type?: string;
  title?: string;
  summary?: string | null;
  text?: string;
  start_offset?: number | null;
  end_offset?: number | null;
  heading_path?: string[];
  keywords?: string[];
  boost?: number;
  visibility?: string;
  embedding_enabled?: boolean;
  full_text_enabled?: boolean;
  status?: string;
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

export async function fetchKnowledgeGraphNodes(): Promise<KnowledgeGraphNode[]> {
  const response = await fetch("/api/web/knowledge/graph/nodes", { credentials: "same-origin" });
  const payload = await readJson<{ nodes: KnowledgeGraphNode[] }>(response, "Не удалось загрузить узлы графа знаний");
  return payload.nodes ?? [];
}

export async function fetchKnowledgeGraphNeighborhood(nodeIdOrStableKey: string, depth = 2): Promise<KnowledgeGraphNeighborhood> {
  const response = await fetch(
    `/api/web/knowledge/graph/nodes/${encodeURIComponent(nodeIdOrStableKey)}/neighborhood?depth=${encodeURIComponent(String(depth))}`,
    { credentials: "same-origin" },
  );
  return readJson<KnowledgeGraphNeighborhood>(response, "Не удалось загрузить связи графа знаний");
}

export async function createKnowledgeGraphNode(payload: Record<string, unknown>) {
  const response = await fetch("/api/web/knowledge/graph/nodes", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ node: KnowledgeGraphNode }>(response, "Не удалось создать узел графа знаний");
}

export async function createKnowledgeGraphEdge(payload: Record<string, unknown>) {
  const response = await fetch("/api/web/knowledge/graph/edges", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ edge: KnowledgeGraphEdge }>(response, "Не удалось создать связь графа знаний");
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

export async function previewKnowledgeSearch(payload: KnowledgeSearchPreviewRequest): Promise<KnowledgeSearchPreviewResult> {
  const response = await fetch("/api/web/knowledge/search", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeSearchPreviewResult>(response, "Не удалось выполнить проверочный поиск");
}

export async function searchKnowledgePortal(payload: KnowledgeSearchPreviewRequest): Promise<KnowledgeSearchPreviewResult> {
  const response = await fetch("/api/knowledge/search", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeSearchPreviewResult>(response, "Не удалось выполнить поиск по базе знаний");
}

export async function fetchKnowledgePortalHome(): Promise<KnowledgePortalHome> {
  const response = await fetch("/api/knowledge/portal/home", { credentials: "same-origin" });
  return readJson<KnowledgePortalHome>(response, "Не удалось загрузить портал базы знаний");
}

export async function fetchKnowledgePortalArticle(slug: string): Promise<KnowledgePortalArticle> {
  const response = await fetch(`/api/knowledge/articles/${encodeURIComponent(slug)}`, { credentials: "same-origin" });
  return readJson<KnowledgePortalArticle>(response, "Не удалось загрузить статью базы знаний");
}

export async function fetchKnowledgePortalCollection(
  collectionType: "space" | "tag",
  code: string,
): Promise<KnowledgePortalCollection> {
  const path = collectionType === "space" ? "spaces" : "tags";
  const response = await fetch(`/api/knowledge/portal/${path}/${encodeURIComponent(code)}`, { credentials: "same-origin" });
  return readJson<KnowledgePortalCollection>(response, "Не удалось загрузить раздел базы знаний");
}

export async function sendKnowledgeArticleFeedback(
  slug: string,
  payload: { helpful: boolean; session_id?: string; result?: string; metadata?: Record<string, unknown> },
): Promise<KnowledgePortalEventResponse> {
  const response = await fetch(`/api/knowledge/articles/${encodeURIComponent(slug)}/feedback`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgePortalEventResponse>(response, "Не удалось отправить оценку статьи");
}

export async function sendKnowledgeArticleCorrectionRequest(
  slug: string,
  payload: { comment?: string; session_id?: string },
): Promise<KnowledgePortalEventResponse> {
  const response = await fetch(`/api/knowledge/articles/${encodeURIComponent(slug)}/correction-request`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgePortalEventResponse>(response, "Не удалось отправить запрос на исправление");
}

export async function setKnowledgePortalBookmark(
  slug: string,
  payload: { session_id?: string } = {},
): Promise<KnowledgePortalBookmarkResponse> {
  const response = await fetch(`/api/knowledge/articles/${encodeURIComponent(slug)}/bookmark`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgePortalBookmarkResponse>(response, "Не удалось добавить статью в закладки");
}

export async function removeKnowledgePortalBookmark(slug: string): Promise<KnowledgePortalBookmarkResponse> {
  const response = await fetch(`/api/knowledge/articles/${encodeURIComponent(slug)}/bookmark`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  return readJson<KnowledgePortalBookmarkResponse>(response, "Не удалось убрать статью из закладок");
}

export async function askKnowledgePortal(payload: KnowledgeSearchPreviewRequest & { query_vector?: number[]; limit?: number }): Promise<KnowledgeAskResult> {
  const response = await fetch("/api/knowledge/ask", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeAskResult>(response, "Не удалось выполнить AI-вопрос по базе знаний");
}

export async function previewKnowledgeAsk(payload: KnowledgeSearchPreviewRequest & { query_vector?: number[]; limit?: number }): Promise<KnowledgeAskResult> {
  const response = await fetch("/api/web/knowledge/ask/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeAskResult>(response, "Не удалось выполнить preview AI-вопроса");
}

export async function retrieveKnowledge(payload: KnowledgeSearchPreviewRequest & { query_vector?: number[]; limit?: number }): Promise<KnowledgeRetrievalResult> {
  const response = await fetch("/api/web/knowledge/retrieve", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeRetrievalResult>(response, "Не удалось выполнить retrieval знаний");
}

export async function previewKnowledgeRetrieval(payload: KnowledgeSearchPreviewRequest & { query_vector?: number[]; limit?: number }): Promise<KnowledgeRetrievalResult> {
  const response = await fetch("/api/web/knowledge/search/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeRetrievalResult>(response, "Не удалось выполнить preview retrieval");
}

export async function fetchKnowledgeSegments(itemIdOrSlug: string): Promise<KnowledgeSegment[]> {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/segments`, { credentials: "same-origin" });
  const payload = await readJson<{ segments: KnowledgeSegment[] }>(response, "Не удалось загрузить сегменты статьи");
  return payload.segments ?? [];
}

export async function createKnowledgeSegment(itemIdOrSlug: string, payload: KnowledgeSegmentPayload) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/segments`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ segment: KnowledgeSegment; display_message?: string }>(response, "Не удалось создать сегмент статьи");
}

export async function updateKnowledgeSegment(segmentId: string, payload: KnowledgeSegmentPayload) {
  const response = await fetch(`/api/web/knowledge/segments/${encodeURIComponent(segmentId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ segment: KnowledgeSegment; display_message?: string }>(response, "Не удалось обновить сегмент статьи");
}

export async function archiveKnowledgeSegment(segmentId: string) {
  const response = await fetch(`/api/web/knowledge/segments/${encodeURIComponent(segmentId)}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  return readJson<{ segment: KnowledgeSegment; display_message?: string }>(response, "Не удалось архивировать сегмент статьи");
}

export async function autoSegmentKnowledgeItem(itemIdOrSlug: string, payload: { version_id?: string; profile_code?: string }) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/segments/auto`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ job: Record<string, unknown>; segments: KnowledgeSegment[]; display_message?: string }>(
    response,
    "Не удалось выполнить авторазметку статьи",
  );
}

export async function revalidateKnowledgeSegments(
  itemIdOrSlug: string,
  payload: { source_version_id: string; target_version_id: string },
) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/segments/revalidate`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ job: Record<string, unknown>; segments: KnowledgeSegment[]; stats: Record<string, number>; display_message?: string }>(
    response,
    "Не удалось перепроверить сегменты статьи",
  );
}

export async function proposeKnowledgeAiSegments(itemIdOrSlug: string, payload: { version_id?: string; profile_code?: string }) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/segments/ai-proposals`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ job: Record<string, unknown>; segments: KnowledgeSegment[]; stats: Record<string, unknown>; display_message?: string }>(
    response,
    "Не удалось создать AI-предложения сегментов",
  );
}

export async function syncKnowledgeSegmentIndex(itemIdOrSlug: string, payload: { version_id?: string }) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/segments/index-sync`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ job: Record<string, unknown>; chunks: Array<Record<string, unknown>>; stats: Record<string, number>; display_message?: string }>(
    response,
    "Не удалось синхронизировать индекс сегментов",
  );
}

export async function fetchKnowledgeIndexingStatus() {
  const response = await fetch("/api/web/knowledge/indexing/status", { credentials: "same-origin" });
  return readJson<{ indexing: KnowledgeIndexingStatus; display_message?: string }>(
    response,
    "Не удалось загрузить статус индексации знаний",
  ).then((payload) => payload.indexing);
}

export async function fetchKnowledgeIndexJobs() {
  const response = await fetch("/api/web/knowledge/indexing/jobs", { credentials: "same-origin" });
  return readJson<{ jobs: KnowledgeIndexJob[]; display_message?: string }>(
    response,
    "Не удалось загрузить задания индексации знаний",
  ).then((payload) => payload.jobs ?? []);
}

export async function reindexKnowledgeItem(payload: { item_id: string; version_id?: string }) {
  const response = await fetch("/api/web/knowledge/indexing/reindex-item", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{
    job: KnowledgeIndexJob;
    embeddings: KnowledgeEmbeddingRecord[];
    stats: Record<string, number>;
    display_message?: string;
  }>(response, "Не удалось запустить индексацию статьи");
}

export async function reindexKnowledgeSegment(payload: { segment_id: string; version_id?: string }) {
  const response = await fetch("/api/web/knowledge/indexing/reindex-segment", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{
    job: KnowledgeIndexJob;
    embeddings: KnowledgeEmbeddingRecord[];
    stats: Record<string, number>;
    display_message?: string;
  }>(response, "Не удалось запустить индексацию сегмента");
}

export async function reindexKnowledgeSpace(payload: { space_id?: string; space_code?: string }) {
  const response = await fetch("/api/web/knowledge/indexing/reindex-space", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{
    job: KnowledgeIndexJob;
    embeddings: KnowledgeEmbeddingRecord[];
    stats: Record<string, number>;
    display_message?: string;
  }>(response, "Не удалось запустить индексацию пространства");
}

export async function reindexKnowledgeAll(payload: { limit?: number } = {}) {
  const response = await fetch("/api/web/knowledge/indexing/reindex-all", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{
    job: KnowledgeIndexJob;
    embeddings: KnowledgeEmbeddingRecord[];
    stats: Record<string, number>;
    display_message?: string;
  }>(response, "Не удалось запустить полную индексацию знаний");
}

export async function createKnowledgeIndexJob(payload: { scope_type: "item" | "segment" | "space" | "all"; scope_ref?: string; limit?: number }) {
  const response = await fetch("/api/web/knowledge/indexing/jobs", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{
    job: KnowledgeIndexJob;
    embeddings: KnowledgeEmbeddingRecord[];
    stats: Record<string, number>;
    display_message?: string;
  }>(response, "Не удалось создать задание индексации знаний");
}

export async function approveKnowledgeAiSegment(segmentId: string) {
  const response = await fetch(`/api/web/knowledge/segments/${encodeURIComponent(segmentId)}/approve`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  return readJson<{ segment: KnowledgeSegment; display_message?: string }>(
    response,
    "Не удалось одобрить AI-предложение сегмента",
  );
}

export async function rejectKnowledgeAiSegment(segmentId: string, payload?: { reason?: string | null }) {
  const response = await fetch(`/api/web/knowledge/segments/${encodeURIComponent(segmentId)}/reject`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  return readJson<{ segment: KnowledgeSegment; display_message?: string }>(
    response,
    "Не удалось отклонить AI-предложение сегмента",
  );
}

export async function fetchKnowledgeSegmentationProfiles(): Promise<KnowledgeSegmentationProfile[]> {
  const response = await fetch("/api/web/knowledge/segmentation-profiles", { credentials: "same-origin" });
  const payload = await readJson<{ profiles: KnowledgeSegmentationProfile[] }>(response, "Не удалось загрузить профили разметки");
  return payload.profiles ?? [];
}

export async function saveKnowledgeSegmentationProfile(payload: Partial<KnowledgeSegmentationProfile> & { code: string; title: string }) {
  const response = await fetch("/api/web/knowledge/segmentation-profiles", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ profile: KnowledgeSegmentationProfile; display_message?: string }>(response, "Не удалось сохранить профиль разметки");
}
