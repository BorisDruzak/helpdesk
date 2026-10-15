export type CatalogSearchResult = {
  title: string;
  description: string;
  category: string;
  offering_full_code: string;
  entry_point_key: string | null;
  help_mode: "guided" | "request";
  match_reason: string;
};

export type CatalogSearchResponse = {
  results: CatalogSearchResult[];
  suggestions: string[];
  corrected_query: string | null;
};

export async function searchRequesterCatalog(query: string, signal: AbortSignal): Promise<CatalogSearchResponse> {
  const response = await fetch(`/api/service-catalog/current?q=${encodeURIComponent(query)}`, {
    credentials: "same-origin", signal,
  });
  if (!response.ok) throw new Error("Не удалось выполнить поиск");
  const payload = await response.json() as { status: string; search?: CatalogSearchResponse };
  if (payload.status !== "ok" || !payload.search) throw new Error("Не удалось выполнить поиск");
  return payload.search;
}
