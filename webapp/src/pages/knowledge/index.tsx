import { BookPlus, Eye, Search } from "lucide-react";
import { useDeferredValue, useState } from "react";

import { Button } from "../../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";
import { SearchField } from "../../components/ui/search-field";
import { knowledgeArticles, knowledgeCategories } from "../../mocks/helpdesk-data";

export function KnowledgeBasePage() {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);

  const visibleArticles = knowledgeArticles.filter((article) =>
    [article.title, article.category, article.summary]
      .join(" ")
      .toLowerCase()
      .includes(deferredQuery.trim().toLowerCase())
  );

  return (
    <section className="space-y-6">
      <PageHeading
        actions={
          <>
            <div className="w-full max-w-[360px]">
              <SearchField onChange={(event) => setQuery(event.target.value)} placeholder="Поиск в базе знаний..." value={query} />
            </div>
            <Button leadingIcon={<BookPlus className="h-4 w-4" />}>Статья</Button>
          </>
        }
        description="База знаний использует тот же светлый каркас: компактные категории слева и удобную ленту статей справа."
        eyebrow="Knowledge"
        title="База знаний"
      />

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Категории</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {knowledgeCategories.map((category, index) => (
              <button
                key={category.label}
                className={`flex w-full items-center justify-between rounded-panel px-4 py-3 text-left transition-colors ${
                  index === 0
                    ? "bg-brand-50 text-brand-800"
                    : "bg-surface-subtle text-slate-700 hover:bg-white"
                }`}
                type="button"
              >
                <span className="font-medium">{category.label}</span>
                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-slate-500">
                  {category.count}
                </span>
              </button>
            ))}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Популярные статьи</CardTitle>
              <CardDescription>Самые читаемые материалы за неделю.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {visibleArticles.map((article) => (
                <div key={article.id} className="flex flex-col gap-4 rounded-[1.1rem] border border-border bg-white px-4 py-4 md:flex-row md:items-start md:justify-between">
                  <div>
                    <p className="font-semibold text-slate-950">{article.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{article.summary}</p>
                    <p className="mt-3 text-xs uppercase tracking-[0.2em] text-brand-700">{article.category}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-4 text-sm text-slate-400">
                    <span className="inline-flex items-center gap-1">
                      <Eye className="h-4 w-4" />
                      {article.views}
                    </span>
                    <span>{article.helpful}</span>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Недавние обновления</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {[
                "Как загрузить и экспортировать отчеты",
                "Решение проблем с входом в систему",
                "Новый порядок настройки уведомлений"
              ].map((item, index) => (
                <div key={item} className="flex items-center justify-between rounded-[1.1rem] bg-surface-subtle px-4 py-4 text-sm">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-brand-700">
                      <Search className="h-4 w-4" />
                    </div>
                    <span className="font-medium text-slate-900">{item}</span>
                  </div>
                  <span className="text-slate-400">{index + 4}.05.2024</span>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
