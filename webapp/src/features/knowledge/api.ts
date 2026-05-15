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
