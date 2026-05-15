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
  items: Array<KnowledgeItem & { reason: string; review_due_at?: string | null }>;
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

export type KnowledgeRolloutPolicy = {
  policy_id: string;
  service_code?: string | null;
  offering_code?: string | null;
  request_template_key?: string | null;
  surface: string;
  enabled: boolean;
  rollout_percent: number;
  reason?: string | null;
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
  const response = await fetch("/api/web/knowledge/review-queue", { credentials: "same-origin" });
  const payload = await readJson<{ review_queue: KnowledgeReviewQueue }>(response, "Не удалось загрузить review queue");
  return payload.review_queue;
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

export async function fetchKnowledgeQuality(): Promise<KnowledgeQualitySummary> {
  const response = await fetch("/api/web/knowledge/quality", { credentials: "same-origin" });
  const payload = await readJson<{ quality: KnowledgeQualitySummary }>(response, "Не удалось загрузить quality score");
  return payload.quality;
}

export async function fetchKnowledgeGaps(): Promise<KnowledgeGapSummary> {
  const response = await fetch("/api/web/knowledge/gaps", { credentials: "same-origin" });
  const payload = await readJson<{ gaps: KnowledgeGapSummary }>(response, "Не удалось загрузить knowledge gaps");
  return payload.gaps;
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
