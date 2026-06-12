import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BookOpen, Search } from "lucide-react";

import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { searchKnowledgePortal, type KnowledgeSearchPreviewResult } from "../../features/knowledge/api";

const fieldClass = "w-full rounded-md border border-slate-200 px-3 py-2 text-sm";

export function KnowledgePortalSearchPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<KnowledgeSearchPreviewResult | null>(null);

  const searchMutation = useMutation({
    mutationFn: () =>
      searchKnowledgePortal({
        query: query.trim(),
        actor_role: "requester",
        surface: "requester_portal",
      }),
    onSuccess: setResult,
  });

  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Portal"
        title="Поиск по базе знаний"
        description="Найдите опубликованные инструкции и решения без создания обращения."
      />

      <Card>
        <CardContent className="p-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <label className="block text-sm font-medium">
              Запрос
              <input
                aria-label="Запрос"
                className={`${fieldClass} mt-1`}
                placeholder="Например: VPN, принтер, доступ"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && query.trim()) {
                    searchMutation.mutate();
                  }
                }}
              />
            </label>
            <Button
              className="self-end"
              leadingIcon={<Search className="h-4 w-4" />}
              disabled={!query.trim() || searchMutation.isPending}
              onClick={() => searchMutation.mutate()}
            >
              Найти
            </Button>
          </div>
        </CardContent>
      </Card>

      {searchMutation.isError ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          Поиск временно недоступен. Попробуйте позже или создайте обращение.
        </div>
      ) : null}

      {result ? (
        <section className="space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            {result.display_message ? <span className="font-medium text-slate-900">{result.display_message}</span> : null}
            <Badge tone={result.ai_used ? "warning" : "success"}>{result.ai_used ? "AI использовался" : "AI не использовался"}</Badge>
            <Badge>{result.effective_mode ?? result.search_mode ?? "режим не задан"}</Badge>
          </div>

          {result.results.length ? (
            <div className="grid gap-3">
              {result.results.map((item, index) => (
                <Card key={item.item_id ?? item.slug ?? `${item.title}-${index}`}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <BookOpen className="h-5 w-5" />
                      {item.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-slate-600">
                    {item.summary ? <p>{item.summary}</p> : null}
                    {item.visibility ? <Badge>{item.visibility}</Badge> : null}
                    {item.slug ? <p className="text-xs text-slate-500">slug: {item.slug}</p> : null}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Ничего не найдено. Измените запрос или создайте обращение, если нужна помощь специалиста.
            </div>
          )}
        </section>
      ) : null}
    </section>
  );
}
