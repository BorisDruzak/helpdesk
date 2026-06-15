import type { ReactNode } from "react";

import { PageHeading } from "../../../components/ui/page-heading";

type GraphWorkbenchLayoutProps = {
  canvas: ReactNode;
  explorer: ReactNode;
  inspector: ReactNode;
};

export function GraphWorkbenchLayout({ canvas, explorer, inspector }: GraphWorkbenchLayoutProps) {
  return (
    <section className="space-y-5 overflow-x-hidden">
      <PageHeading
        eyebrow="Редактор базы знаний"
        title="Граф знаний"
        description="Визуальный редактор узлов, связей и схемы размещения для администратора базы знаний."
      />
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-600">
        <p className="font-semibold text-slate-900">Advanced workbench</p>
        <p>Обычное создание и сохранение статьи не требует работы с графом; используйте эту страницу для related articles, duplicates, supersedes, known error/workaround и service/article связей.</p>
      </div>
      <div className="grid min-w-0 gap-4 xl:grid-cols-[260px_minmax(420px,1fr)_300px] 2xl:grid-cols-[300px_minmax(620px,1fr)_340px]">
        <aside className="min-w-0 space-y-4">{explorer}</aside>
        <main className="min-w-0">{canvas}</main>
        <aside className="surface-panel sticky top-4 max-h-[calc(100vh-2rem)] min-w-0 overflow-y-auto p-5">
          <div className="mb-4">
            <h2 className="text-xl font-semibold tracking-tight text-slate-950">Инспектор</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">Свойства выбранного узла или связи, публикация изменений и опасные действия.</p>
          </div>
          {inspector}
        </aside>
      </div>
    </section>
  );
}
