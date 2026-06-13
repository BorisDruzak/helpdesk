import { Link } from "react-router-dom";
import { Bot, DatabaseZap, GitBranch, PenTool, Search, UploadCloud } from "lucide-react";

import { PageHeading } from "../../components/ui/page-heading";
import { KnowledgeOpsDashboardPanel } from "../../features/knowledge/ops-dashboard-panel";

const workbenchLinks = [
  { href: "/app/admin/knowledge/studio", icon: PenTool, label: "Студия", text: "Редактировать статью, версию, разметку и публикацию." },
  { href: "/app/admin/knowledge/import", icon: UploadCloud, label: "Импорт", text: "Создать review draft из текста, файла, URL или git." },
  { href: "/app/admin/knowledge/graph", icon: GitBranch, label: "Граф", text: "Построить связи и сохранить layout графа." },
  { href: "/app/admin/knowledge/search-settings", icon: Search, label: "Поиск", text: "Настроить retrieval и проверить выдачу." },
  { href: "/app/admin/knowledge/indexing", icon: DatabaseZap, label: "Индексация", text: "Проверить очередь и запустить reindex." },
  { href: "/app/admin/knowledge/ai", icon: Bot, label: "AI", text: "Провайдеры, профили, политики и audit." },
];

export function AdminKnowledgePage() {
  return (
    <section className="space-y-6">
      <PageHeading
        eyebrow="Knowledge Operations Center"
        title="Операции базы знаний"
        description="Админский обзор здоровья платформы знаний и быстрые переходы к отдельным рабочим сценариям."
      />

      <nav aria-label="Основные разделы базы знаний" className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
        {workbenchLinks.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              className="surface-panel flex min-h-28 flex-col gap-2 p-4 text-sm transition-colors hover:border-brand-200 hover:bg-brand-50"
              key={item.href}
              to={item.href}
            >
              <span className="flex items-center gap-2 font-semibold text-slate-950">
                <Icon className="h-4 w-4 text-brand-700" />
                {item.label}
              </span>
              <span className="text-xs leading-5 text-slate-500">{item.text}</span>
            </Link>
          );
        })}
      </nav>

      <KnowledgeOpsDashboardPanel />
    </section>
  );
}
