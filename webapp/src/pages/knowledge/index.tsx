import { BookOpenCheck } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../../components/ui/card";
import { PageHeading } from "../../components/ui/page-heading";


export function KnowledgeBasePage() {
  return (
    <section className="space-y-6">
      <PageHeading
        description="Раздел базы знаний остаётся в навигации, но честно помечен как следующий этап. Сейчас основная волна идёт на реальные рабочие места, отчёты и настройки."
        eyebrow="Knowledge"
        title="База знаний"
      />

      <Card>
        <CardHeader>
          <CardTitle>В разработке</CardTitle>
          <CardDescription>Текущий webapp уже использует реальный backend для tickets, admin, reports и settings. Knowledge base будет следующей отдельной волной.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col items-center gap-4 py-10 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-brand-50 text-brand-700">
            <BookOpenCheck className="h-7 w-7" />
          </div>
          <div className="max-w-xl">
            <p className="text-base font-semibold text-slate-950">База знаний ещё не подключена</p>
            <p className="mt-2 text-sm leading-7 text-slate-500">
              Тут появится отдельный real-data раздел со статьями, категориями и поиском, когда подготовим backend-контур для knowledge catalog.
            </p>
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
