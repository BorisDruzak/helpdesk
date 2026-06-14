export type KnowledgeSpace = {
  space_id: string;
  code: string;
  title: string;
  description?: string | null;
  visibility: string;
  lifecycle_status: string;
  owner_actor_id?: string | null;
  default_reviewer_actor_id?: string | null;
  default_review_period_days?: number | null;
  allowed_item_types?: string[];
  allow_publication?: boolean;
  allow_ingestion?: boolean;
  allow_rag?: boolean;
  metadata?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
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

export type KnowledgeAudienceRuleTargetType =
  | "person"
  | "department"
  | "department_tree"
  | "location"
  | "access_group"
  | "audience_group"
  | "role"
  | "service";

export type KnowledgeAudienceRule = {
  rule_id?: string | null;
  subject_type: "item" | "space" | string;
  subject_id: string;
  target_type: KnowledgeAudienceRuleTargetType;
  target_id: string;
  effect?: "allow" | string;
  include_children?: boolean;
  priority?: number;
  status?: "active" | "disabled" | string;
  reason?: string | null;
  metadata_json?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
};

export type KnowledgeAudienceRuleInput = Omit<
  KnowledgeAudienceRule,
  "created_at" | "created_by" | "rule_id" | "subject_id" | "subject_type" | "updated_at" | "updated_by"
> & {
  rule_id?: string | null;
};

export type KnowledgeAudienceDecision = {
  allowed: boolean;
  reason_code: string;
  matched_rule_ids?: string[];
};

export type KnowledgeAudiencePreview = {
  subject?: { subject_type: string; subject_id: string };
  item?: Record<string, unknown>;
  space?: Record<string, unknown> | null;
  audience?: Record<string, unknown>;
  decision: KnowledgeAudienceDecision;
  safe_payload?: Record<string, unknown>;
};

export type KnowledgeAudienceExplain = KnowledgeAudiencePreview & {
  rules?: KnowledgeAudienceRule[];
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
  weight?: number;
  confidence_score?: number | null;
  visibility: string;
  status?: string | null;
  source_kind?: string | null;
  source_ref?: string | null;
};

export type KnowledgeGraphNeighborhood = {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
};

export type KnowledgeGraphSearchResult = {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
};

export type KnowledgeGraphLayout = {
  layout_id?: string | null;
  scope_type: string;
  scope_ref: string;
  layout_json: Record<string, unknown>;
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

export type KnowledgeOpsMetric = {
  total: number;
  [key: string]: unknown;
};

export type KnowledgeOpsSummary = {
  status: "ok" | "degraded" | string;
  generated_at: string;
  coverage: {
    spaces: KnowledgeOpsMetric;
    published_articles: KnowledgeOpsMetric;
    requester_safe: KnowledgeOpsMetric;
    support_runbooks: KnowledgeOpsMetric;
    services_without_kb: KnowledgeOpsMetric;
  };
  quality: {
    average_score: number;
    low_quality_count: KnowledgeOpsMetric;
    stale_review_count: KnowledgeOpsMetric;
    missing_owner_reviewer_count: KnowledgeOpsMetric;
    unsafe_requester_safe_blockers: KnowledgeOpsMetric;
  };
  search: {
    zero_result_searches: KnowledgeOpsMetric;
    top_queries: Array<{ query: string; count: number }>;
    fallback_count: KnowledgeOpsMetric;
    ai_disabled_count: KnowledgeOpsMetric;
    vector_usage_count: KnowledgeOpsMetric;
    rerank_usage_count: KnowledgeOpsMetric;
  };
  rag: {
    answer_count: KnowledgeOpsMetric;
    no_answer_count: KnowledgeOpsMetric;
    provider_failures: KnowledgeOpsMetric;
    citation_validation_failures: KnowledgeOpsMetric;
  };
  indexing: {
    queued: KnowledgeOpsMetric;
    failed: KnowledgeOpsMetric;
    stale_embeddings: KnowledgeOpsMetric;
    disabled: KnowledgeOpsMetric;
    vector_enabled?: boolean;
    embedding_model?: string | null;
  };
  ai: {
    provider_health: { status: string; failed_count?: number; ok_count?: number };
    model_profile_status: { active_count: number; disabled_count: number };
    policy_blocks: KnowledgeOpsMetric;
  };
  graph: {
    orphan_nodes: KnowledgeOpsMetric;
    pending_proposals: KnowledgeOpsMetric;
    contradiction_duplicate_findings: KnowledgeOpsMetric;
  };
  review: {
    assigned_open: KnowledgeOpsMetric;
    overdue: KnowledgeOpsMetric;
  };
  observer: {
    degradations: Array<{
      code: string;
      severity: string;
      source: string;
      count: number;
      status: string;
      message: string;
    }>;
  };
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

export type KnowledgeEditorEvent = {
  event_id: string;
  item_id?: string;
  version_id?: string | null;
  event_type: string;
  source_surface?: string;
  summary?: string | null;
  actor_id?: string | null;
  actor_role?: string | null;
  payload?: Record<string, unknown>;
  created_at?: string | null;
};

export type KnowledgeVersionDiffCacheEntry = {
  diff_id: string;
  item_id?: string;
  from_version_id?: string | null;
  to_version_id: string;
  added_lines: number;
  removed_lines: number;
  changed_lines?: number;
  summary?: Record<string, unknown>;
  content_hash?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type KnowledgeEditorHistory = {
  status?: string;
  events: KnowledgeEditorEvent[];
  diff_cache: KnowledgeVersionDiffCacheEntry[];
};

export type KnowledgeTaxonomyTerm = {
  term_id: string;
  space_id: string;
  term_type: string;
  code: string;
  title: string;
  description?: string | null;
  parent_term_id?: string | null;
  visibility: string;
  status: string;
  sort_order?: number;
  metadata?: Record<string, unknown>;
};

export type KnowledgePropertyDefinition = {
  property_id: string;
  space_id: string;
  code: string;
  title: string;
  description?: string | null;
  value_type: string;
  required: boolean;
  allowed_values?: unknown[];
  applies_to_item_types?: string[];
  quality_weight?: number;
  status: string;
  metadata?: Record<string, unknown>;
};

export type KnowledgeApplicabilityRule = {
  rule_id: string;
  item_id: string;
  scope_type: string;
  scope_ref: string;
  include_mode: "include" | "exclude" | string;
  priority: number;
  conditions?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
};

export type KnowledgeQualityModel = {
  model_id?: string | null;
  space_id?: string | null;
  code: string;
  title: string;
  weights?: Record<string, number>;
  thresholds?: Record<string, number>;
  status: string;
  is_default: boolean;
  metadata?: Record<string, unknown>;
};

export type KnowledgeItemMetadata = {
  item_id: string;
  space_id: string;
  slug: string;
  title: string;
  properties: Record<string, unknown>;
  property_values?: Array<{
    item_property_id: string;
    property_id: string;
    code: string;
    title: string;
    value: unknown;
  }>;
  taxonomy_terms: KnowledgeTaxonomyTerm[];
  applicability_rules: KnowledgeApplicabilityRule[];
};

export type KnowledgeMetadataBundle = {
  spaces: Array<Pick<KnowledgeSpace, "space_id" | "code" | "title" | "visibility" | "lifecycle_status">>;
  taxonomy_terms: KnowledgeTaxonomyTerm[];
  property_definitions: KnowledgePropertyDefinition[];
  applicability_rules: KnowledgeApplicabilityRule[];
  quality_models: KnowledgeQualityModel[];
  item_metadata: KnowledgeItemMetadata[];
  summary?: {
    taxonomy_terms_total: number;
    taxonomy_terms_active: number;
    property_definitions_total: number;
    property_definitions_active: number;
    applicability_rules_total: number;
    applicability_rules_active: number;
    quality_models_total: number;
    quality_models_active: number;
    item_metadata_total: number;
  };
};

export type KnowledgeServiceCatalogOption = {
  label: string;
  service_code?: string | null;
  type: "service" | "offering";
  value: string;
};

export type KnowledgeQualitySummary = {
  average_quality_score: number;
  quality_model?: KnowledgeQualityModel;
  items: Array<
    KnowledgeItem & {
      quality_score: number;
      dimensions?: Record<string, number>;
      issues: string[];
      feedback?: Record<string, number>;
      quality_model?: KnowledgeQualityModel;
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

export type KnowledgeAiProposal = {
  proposal_id: string;
  proposal_type: string;
  target_kind: string;
  target_ref: string;
  title: string;
  rationale?: string | null;
  proposed_payload?: Record<string, unknown>;
  status: string;
  confidence_score?: number | null;
  visibility?: string | null;
  source_kind?: string | null;
  source_ref?: string | null;
  applied_refs?: Record<string, unknown>;
  review_note?: string | null;
  created_by?: string | null;
  reviewed_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  reviewed_at?: string | null;
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

export type KnowledgeImportPreview = {
  source_kind: string;
  source_name: string;
  body_format?: string;
  detected_title: string;
  word_count?: number;
  section_count: number;
  sections: Array<{ heading: string; preview?: string }>;
  remote_source?: {
    source_kind?: string;
    host?: string | null;
    path?: string;
    repo?: string;
    ref?: string;
    file_count?: number;
    bytes?: number;
  };
  ai_enrichment: { enabled: boolean; status: string; proposals?: Array<Record<string, unknown>> };
};

export type KnowledgeImportDraftResult = {
  preview: KnowledgeImportPreview;
  ai_enrichment: KnowledgeImportPreview["ai_enrichment"];
  segmentation?: {
    enabled: boolean;
    status: string;
    profile_code?: string;
    job?: Record<string, unknown>;
    segments?: Array<Record<string, unknown>>;
  };
  indexing?: {
    enabled: boolean;
    status: string;
    reason?: string;
    job?: Record<string, unknown>;
    stats?: Record<string, number>;
    embeddings?: Array<Record<string, unknown>>;
  };
  job: { job_id: string; status: string };
  item: KnowledgeItem;
  version: KnowledgeItemVersion;
  chunk_count?: number;
};

export type KnowledgeImportJob = {
  job_id: string;
  space_id: string;
  space?: {
    space_id: string;
    code: string;
    title: string;
    visibility: string;
  };
  source_kind: string;
  source_name: string;
  source_uri?: string | null;
  source_hash?: string | null;
  status: string;
  created_item_id?: string | null;
  created_version_id?: string | null;
  error_message_redacted?: string | null;
  stats_json?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  completed_at?: string | null;
};

export type SupportTicketKnowledgeRequesterAttempt = {
  item_id: string;
  version_id?: string | null;
  result: string;
  surface: string;
  occurred_at: string;
};

export type SupportTicketKnowledgeSuggestions = {
  ticket_id: string;
  requester_attempts: SupportTicketKnowledgeRequesterAttempt[];
  similar_tickets: Array<{
    id: string;
    number: string | null;
    subject: string;
    resolution_summary: string | null;
  }>;
  articles: Array<{
    id: string;
    title: string;
    url: string | null;
  }>;
  ai_summary: {
    text: string | null;
    sources: string[];
    confidence?: string;
    source_count?: number;
  };
  diagnostics?: Record<string, unknown>;
};

export type SupportTicketKnowledgeDraft = {
  title: string;
  problem: string;
  resolution: string;
  repeat_guidance: string;
  source_passport_id: number;
  item_id?: string | null;
  version_id?: string | null;
  status?: string | null;
  item_type?: string | null;
  edit_url?: string | null;
  warnings?: string[];
  bindings?: Array<Record<string, unknown>>;
};

async function readJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.details ?? payload?.error ?? fallbackMessage);
  }
  return payload as T;
}

function unwrapAdminData<T>(payload: ({ data?: T } & Record<string, unknown>) | T): T {
  if (payload && typeof payload === "object" && "data" in payload) {
    return ((payload as { data?: T }).data ?? payload) as T;
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

export async function fetchKnowledgeAudienceRules(subjectType: "item" | "space", subjectId: string): Promise<KnowledgeAudienceRule[]> {
  const params = new URLSearchParams({
    subject_type: subjectType,
    subject_id: subjectId,
  });
  const response = await fetch(`/api/web/admin/knowledge/audience-rules?${params.toString()}`, { credentials: "same-origin" });
  const payload = await readJson<{ data?: { rules: KnowledgeAudienceRule[] }; rules?: KnowledgeAudienceRule[] }>(
    response,
    "Не удалось загрузить правила видимости знаний",
  );
  return payload.data?.rules ?? payload.rules ?? [];
}

export async function fetchKnowledgeAudienceRulesBySubjectType(subjectType: "item" | "space"): Promise<KnowledgeAudienceRule[]> {
  const params = new URLSearchParams({ subject_type: subjectType });
  const response = await fetch(`/api/web/admin/knowledge/audience-rules?${params.toString()}`, { credentials: "same-origin" });
  const payload = await readJson<{ data?: { rules?: KnowledgeAudienceRule[] }; rules?: KnowledgeAudienceRule[] }>(
    response,
    "Не удалось загрузить правила видимости знаний",
  );
  return payload.data?.rules ?? payload.rules ?? [];
}

export async function replaceKnowledgeAudienceRules(payload: {
  subject_type: "item" | "space";
  subject_id: string;
  rules: KnowledgeAudienceRuleInput[];
  reason?: string | null;
}): Promise<KnowledgeAudienceRule[]> {
  const response = await fetch("/api/web/admin/knowledge/audience-rules", {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<{ data?: { rules: KnowledgeAudienceRule[] }; rules?: KnowledgeAudienceRule[] }>(
    response,
    "Не удалось сохранить правила видимости знаний",
  );
  return result.data?.rules ?? result.rules ?? [];
}

export async function previewKnowledgeAudienceRules(payload: {
  subject_type: "item" | "space";
  subject_id: string;
  actor_id?: string | null;
  actor_role?: string;
  rules?: KnowledgeAudienceRuleInput[];
  service_context?: Record<string, unknown> | null;
}): Promise<KnowledgeAudiencePreview> {
  const response = await fetch("/api/web/admin/knowledge/audience-rules/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<{ data?: { preview: KnowledgeAudiencePreview }; preview?: KnowledgeAudiencePreview }>(
    response,
    "Не удалось выполнить предпросмотр видимости знаний",
  );
  return unwrapAdminData(result).preview;
}

export async function explainKnowledgeAccess(params: {
  item_id: string;
  actor_id?: string | null;
  actor_role?: string;
  service_code?: string | null;
}): Promise<KnowledgeAudienceExplain> {
  const searchParams = new URLSearchParams({
    item_id: params.item_id,
    actor_role: params.actor_role ?? "user",
  });
  if (params.actor_id) {
    searchParams.set("actor_id", params.actor_id);
  }
  if (params.service_code) {
    searchParams.set("service_code", params.service_code);
  }
  const response = await fetch(`/api/web/admin/knowledge/access/explain?${searchParams.toString()}`, { credentials: "same-origin" });
  const result = await readJson<{ data?: { explain: KnowledgeAudienceExplain }; explain?: KnowledgeAudienceExplain }>(
    response,
    "Не удалось объяснить доступ к статье",
  );
  return unwrapAdminData(result).explain;
}

export async function previewKnowledgeImport(payload: Record<string, unknown>): Promise<KnowledgeImportPreview> {
  const response = await fetch("/api/web/knowledge/import/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const result = await readJson<{ preview: KnowledgeImportPreview }>(response, "Не удалось выполнить preview импорта");
  return result.preview;
}

export async function createKnowledgeImportDrafts(payload: Record<string, unknown>): Promise<KnowledgeImportDraftResult> {
  const response = await fetch("/api/web/knowledge/import/create-drafts", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeImportDraftResult>(response, "Не удалось создать черновик из импорта");
}

export async function fetchKnowledgeImportJobs(): Promise<KnowledgeImportJob[]> {
  const response = await fetch("/api/web/knowledge/import/jobs", { credentials: "same-origin" });
  const payload = await readJson<{ jobs: KnowledgeImportJob[] }>(response, "Не удалось загрузить задания импорта");
  return payload.jobs ?? [];
}

export async function fetchKnowledgeImportJob(jobId: string): Promise<KnowledgeImportJob> {
  const response = await fetch(`/api/web/knowledge/import/jobs/${encodeURIComponent(jobId)}`, { credentials: "same-origin" });
  const payload = await readJson<{ job: KnowledgeImportJob }>(response, "Не удалось загрузить задание импорта");
  return payload.job;
}

export async function linkKnowledgeArticleToTicket(
  ticketId: string,
  payload: { article_ref: string; title?: string; source?: string },
): Promise<{ kb_link: Record<string, unknown> }> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/kb_links`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ kb_link: Record<string, unknown> }>(response, "Не удалось связать статью с тикетом");
}

export async function recordKnowledgeSupportFeedback(payload: Record<string, unknown>): Promise<{ event: Record<string, unknown> }> {
  const response = await fetch("/api/knowledge/feedback", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ event: Record<string, unknown> }>(response, "Не удалось записать использование знания");
}

export async function fetchSupportTicketKnowledgeSuggestions(ticketId: string): Promise<SupportTicketKnowledgeSuggestions> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/knowledge-suggestions`, {
    credentials: "same-origin",
  });
  const payload = await readJson<{ status: string; data: SupportTicketKnowledgeSuggestions }>(response, "Не удалось загрузить знания по тикету");
  return payload.data;
}

export async function createSupportTicketKnowledgeDraft(ticketId: string): Promise<SupportTicketKnowledgeDraft> {
  const response = await fetch(`/api/web/support/tickets/${encodeURIComponent(ticketId)}/passport/knowledge-draft`, {
    method: "POST",
    credentials: "same-origin",
  });
  const payload = await readJson<{ status: string; data: SupportTicketKnowledgeDraft }>(response, "Не удалось подготовить черновик знания");
  return payload.data;
}

export async function fetchKnowledgeGraphNodes(): Promise<KnowledgeGraphNode[]> {
  const response = await fetch("/api/web/knowledge/graph/nodes", { credentials: "same-origin" });
  const payload = await readJson<{ nodes: KnowledgeGraphNode[] }>(response, "Не удалось загрузить узлы графа знаний");
  return payload.nodes ?? [];
}

export async function searchKnowledgeGraph(query: string): Promise<KnowledgeGraphSearchResult> {
  const response = await fetch(`/api/web/knowledge/graph/search?q=${encodeURIComponent(query)}`, { credentials: "same-origin" });
  return readJson<KnowledgeGraphSearchResult>(response, "Не удалось выполнить поиск по графу знаний");
}

export async function fetchKnowledgeGraphNeighborhood(nodeIdOrStableKey: string, depth = 2): Promise<KnowledgeGraphNeighborhood> {
  const response = await fetch(
    `/api/web/knowledge/graph/nodes/${encodeURIComponent(nodeIdOrStableKey)}/neighborhood?depth=${encodeURIComponent(String(depth))}`,
    { credentials: "same-origin" },
  );
  return readJson<KnowledgeGraphNeighborhood>(response, "Не удалось загрузить связи графа знаний");
}

export async function fetchKnowledgeGraphLayout(scope = "default"): Promise<KnowledgeGraphLayout> {
  const response = await fetch(`/api/web/knowledge/graph/layouts/${encodeURIComponent(scope)}`, { credentials: "same-origin" });
  const payload = await readJson<{ layout: KnowledgeGraphLayout }>(response, "Не удалось загрузить схему размещения графа знаний");
  return payload.layout;
}

export async function saveKnowledgeGraphLayout(scope: string, layoutJson: Record<string, unknown>, scopeType = "graph") {
  const response = await fetch(`/api/web/knowledge/graph/layouts/${encodeURIComponent(scope)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout_json: layoutJson, scope_type: scopeType }),
  });
  return readJson<{ layout: KnowledgeGraphLayout }>(response, "Не удалось сохранить схему размещения графа знаний");
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

export async function updateKnowledgeGraphNode(nodeIdOrStableKey: string, payload: Record<string, unknown>) {
  const response = await fetch(`/api/web/knowledge/graph/nodes/${encodeURIComponent(nodeIdOrStableKey)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ node: KnowledgeGraphNode; display_message?: string }>(response, "Не удалось обновить узел графа знаний");
}

export async function deleteKnowledgeGraphNode(nodeIdOrStableKey: string) {
  const response = await fetch(`/api/web/knowledge/graph/nodes/${encodeURIComponent(nodeIdOrStableKey)}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  return readJson<{ node: KnowledgeGraphNode; display_message?: string }>(response, "Не удалось архивировать узел графа знаний");
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

export async function fetchKnowledgeGraphEdge(edgeId: string) {
  const response = await fetch(`/api/web/knowledge/graph/edges/${encodeURIComponent(edgeId)}`, { credentials: "same-origin" });
  return readJson<{ edge: KnowledgeGraphEdge }>(response, "Не удалось загрузить связь графа знаний");
}

export async function updateKnowledgeGraphEdge(edgeId: string, payload: Record<string, unknown>) {
  const response = await fetch(`/api/web/knowledge/graph/edges/${encodeURIComponent(edgeId)}`, {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ edge: KnowledgeGraphEdge; display_message?: string }>(response, "Не удалось обновить связь графа знаний");
}

export async function deleteKnowledgeGraphEdge(edgeId: string) {
  const response = await fetch(`/api/web/knowledge/graph/edges/${encodeURIComponent(edgeId)}`, {
    method: "DELETE",
    credentials: "same-origin",
  });
  return readJson<{ edge: KnowledgeGraphEdge; display_message?: string }>(response, "Не удалось архивировать связь графа знаний");
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

export async function fetchKnowledgeEditorHistory(itemIdOrSlug: string): Promise<KnowledgeEditorHistory> {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/editor-history`, {
    credentials: "same-origin",
  });
  const payload = await readJson<KnowledgeEditorHistory>(response, "Не удалось загрузить историю редактора");
  return {
    status: payload.status,
    events: payload.events ?? [],
    diff_cache: payload.diff_cache ?? [],
  };
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

export async function fetchKnowledgeOpsSummary(): Promise<KnowledgeOpsSummary> {
  const response = await fetch("/api/web/knowledge/ops/summary", { credentials: "same-origin" });
  const payload = await readJson<{ summary: KnowledgeOpsSummary }>(response, "Не удалось загрузить Knowledge Ops summary");
  return payload.summary;
}

export async function fetchKnowledgeMetadata(): Promise<KnowledgeMetadataBundle> {
  const response = await fetch("/api/web/knowledge/metadata", { credentials: "same-origin" });
  const payload = await readJson<{ metadata: KnowledgeMetadataBundle }>(response, "Не удалось загрузить модель метаданных знаний");
  return payload.metadata;
}

export async function fetchKnowledgeServiceCatalogOptions(): Promise<KnowledgeServiceCatalogOption[]> {
  const response = await fetch("/api/service-catalog/current", { credentials: "same-origin" });
  const payload = await readJson<{
    services?: Array<{
      service_code: string;
      title?: string | null;
      offerings?: Array<{ full_code?: string | null; offering_code?: string | null; title?: string | null }>;
    }>;
  }>(response, "Не удалось загрузить каталог услуг");
  return (payload.services ?? []).flatMap((service) => [
    {
      label: service.title ? `${service.title} · ${service.service_code}` : service.service_code,
      service_code: service.service_code,
      type: "service" as const,
      value: service.service_code,
    },
    ...(service.offerings ?? [])
      .map((offering) => ({
        label: offering.title ? `${offering.title} · ${offering.full_code ?? offering.offering_code ?? ""}` : offering.full_code ?? offering.offering_code ?? "",
        service_code: service.service_code,
        type: "offering" as const,
        value: offering.full_code ?? offering.offering_code ?? "",
      }))
      .filter((option) => option.value),
  ]);
}

export async function fetchKnowledgeItemMetadata(itemIdOrSlug: string): Promise<KnowledgeItemMetadata> {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/metadata`, { credentials: "same-origin" });
  const payload = await readJson<{ item_metadata: KnowledgeItemMetadata }>(response, "Не удалось загрузить метаданные статьи");
  return payload.item_metadata;
}

export async function saveKnowledgeTaxonomyTerm(payload: Partial<KnowledgeTaxonomyTerm> & { space_id: string; term_type: string; code: string; title: string }) {
  const response = await fetch("/api/web/knowledge/taxonomy", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ term: KnowledgeTaxonomyTerm }>(response, "Не удалось сохранить термин таксономии");
}

export async function saveKnowledgePropertyDefinition(
  payload: Partial<KnowledgePropertyDefinition> & { space_id: string; code: string; title: string; value_type: string },
) {
  const response = await fetch("/api/web/knowledge/properties", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ property: KnowledgePropertyDefinition }>(response, "Не удалось сохранить свойство знаний");
}

export async function saveKnowledgeItemMetadata(itemIdOrSlug: string, payload: { properties?: Record<string, unknown>; taxonomy_term_ids?: string[] }) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/metadata`, {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ item_metadata: KnowledgeItemMetadata }>(response, "Не удалось сохранить метаданные статьи");
}

export async function saveKnowledgeApplicabilityRules(itemIdOrSlug: string, rules: Array<Partial<KnowledgeApplicabilityRule>>) {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/applicability`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rules }),
  });
  return readJson<{ rules: KnowledgeApplicabilityRule[] }>(response, "Не удалось сохранить правила применимости");
}

export async function fetchKnowledgeApplicabilityRules(itemIdOrSlug: string): Promise<KnowledgeApplicabilityRule[]> {
  const response = await fetch(`/api/web/knowledge/items/${encodeURIComponent(itemIdOrSlug)}/applicability`, { credentials: "same-origin" });
  const payload = await readJson<{ rules: KnowledgeApplicabilityRule[] }>(response, "Не удалось загрузить правила применимости");
  return payload.rules ?? [];
}

export async function saveKnowledgeQualityModel(payload: Partial<KnowledgeQualityModel> & { code: string; title: string }) {
  const response = await fetch("/api/web/knowledge/quality-models", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ quality_model: KnowledgeQualityModel }>(response, "Не удалось сохранить модель качества знаний");
}

export async function fetchKnowledgeContentPacks(): Promise<KnowledgeContentPack[]> {
  const response = await fetch("/api/web/knowledge/content-packs", { credentials: "same-origin" });
  const payload = await readJson<{ packs: KnowledgeContentPack[] }>(response, "Не удалось загрузить пакеты контента знаний");
  return payload.packs ?? [];
}

export async function applyKnowledgeContentPack(payload: { pack: Record<string, unknown>; dry_run?: boolean; force?: boolean }) {
  const response = await fetch("/api/web/knowledge/content-packs/apply", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ result: KnowledgeContentPackApplyResult }>(response, "Не удалось применить пакет контента знаний");
}

export async function retireKnowledgeContentPack(packCode: string) {
  const response = await fetch(`/api/web/knowledge/content-packs/${encodeURIComponent(packCode)}/retire`, {
    method: "POST",
    credentials: "same-origin",
  });
  return readJson<{ result: Record<string, unknown> }>(response, "Не удалось вывести пакет контента знаний из использования");
}

export async function fetchKnowledgeTemplates(): Promise<KnowledgeTemplate[]> {
  const response = await fetch("/api/web/knowledge/templates", { credentials: "same-origin" });
  const payload = await readJson<{ templates: KnowledgeTemplate[] }>(response, "Не удалось загрузить шаблоны знаний");
  return payload.templates ?? [];
}

export async function fetchKnowledgeReviewQueue(): Promise<KnowledgeReviewQueue> {
  const response = await fetch("/api/web/knowledge/review/tasks", { credentials: "same-origin" });
  const payload = await readJson<{ review_queue: KnowledgeReviewQueue }>(response, "Не удалось загрузить очередь проверки знаний");
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
  return readJson<{ task: KnowledgeReviewTask }>(response, "Не удалось обновить задачу проверки знания");
}

export async function fetchKnowledgeQuality(): Promise<KnowledgeQualitySummary> {
  const response = await fetch("/api/web/knowledge/quality", { credentials: "same-origin" });
  const payload = await readJson<{ quality: KnowledgeQualitySummary }>(response, "Не удалось загрузить оценку качества знаний");
  return payload.quality;
}

export async function fetchKnowledgeGaps(): Promise<KnowledgeGapSummary> {
  const response = await fetch("/api/web/knowledge/gap-findings", { credentials: "same-origin" });
  const payload = await readJson<{ gaps: KnowledgeGapSummary }>(response, "Не удалось загрузить пробелы базы знаний");
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
  return readJson<{ findings: KnowledgeGapFinding[]; count: number }>(response, "Не удалось пересчитать пробелы базы знаний");
}

export async function submitKnowledgeGapAction(findingId: string, action: "accept" | "dismiss" | "create-draft", payload?: Record<string, unknown>) {
  const response = await fetch(`/api/web/knowledge/gaps/${encodeURIComponent(findingId)}/${encodeURIComponent(action)}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  return readJson<Record<string, unknown>>(response, "Не удалось обновить пробел базы знаний");
}

export async function fetchKnowledgeRolloutPolicies(): Promise<KnowledgeRolloutPolicy[]> {
  const response = await fetch("/api/web/knowledge/rollout-policies", { credentials: "same-origin" });
  const payload = await readJson<{ policies: KnowledgeRolloutPolicy[] }>(response, "Не удалось загрузить политики показа знаний");
  return payload.policies ?? [];
}

export async function saveKnowledgeRolloutPolicy(payload: Partial<KnowledgeRolloutPolicy>) {
  const response = await fetch("/api/web/knowledge/rollout-policies", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ policy: KnowledgeRolloutPolicy }>(response, "Не удалось сохранить политику показа знаний");
}

export async function fetchKnowledgeAiProviders(): Promise<KnowledgeAiProvider[]> {
  const response = await fetch("/api/web/knowledge/ai/providers", { credentials: "same-origin" });
  const payload = await readJson<{ providers: KnowledgeAiProvider[] }>(response, "Не удалось загрузить провайдеры AI");
  return payload.providers ?? [];
}

export async function fetchKnowledgeAiProposals(filters: { target_kind?: string; status?: string; limit?: number } = {}): Promise<KnowledgeAiProposal[]> {
  const params = new URLSearchParams();
  if (filters.target_kind) {
    params.set("target_kind", filters.target_kind);
  }
  if (filters.status) {
    params.set("status", filters.status);
  }
  if (filters.limit) {
    params.set("limit", String(filters.limit));
  }
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`/api/web/knowledge/ai/proposals${suffix}`, { credentials: "same-origin" });
  const payload = await readJson<{ proposals: KnowledgeAiProposal[] }>(response, "Не удалось загрузить AI proposals");
  return payload.proposals ?? [];
}

export async function createKnowledgeAiProposal(payload: Partial<KnowledgeAiProposal> & { proposal_type: string; target_kind: string; target_ref: string; title: string }) {
  const response = await fetch("/api/web/knowledge/ai/proposals", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ proposal: KnowledgeAiProposal }>(response, "Не удалось создать AI proposal");
}

export async function reviewKnowledgeAiProposal(proposalId: string, payload: { action: "approve" | "reject" | "comment"; note?: string | null }) {
  const response = await fetch(`/api/web/knowledge/ai/proposals/${encodeURIComponent(proposalId)}/review`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<{ proposal: KnowledgeAiProposal }>(response, "Не удалось выполнить review AI proposal");
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
  return readJson<KnowledgeAskResult>(response, "Не удалось выполнить предпросмотр AI-вопроса");
}

export async function retrieveKnowledge(payload: KnowledgeSearchPreviewRequest & { query_vector?: number[]; limit?: number }): Promise<KnowledgeRetrievalResult> {
  const response = await fetch("/api/web/knowledge/retrieve", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeRetrievalResult>(response, "Не удалось выполнить подбор знаний");
}

export async function previewKnowledgeRetrieval(payload: KnowledgeSearchPreviewRequest & { query_vector?: number[]; limit?: number }): Promise<KnowledgeRetrievalResult> {
  const response = await fetch("/api/web/knowledge/search/preview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return readJson<KnowledgeRetrievalResult>(response, "Не удалось выполнить предпросмотр подбора знаний");
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
