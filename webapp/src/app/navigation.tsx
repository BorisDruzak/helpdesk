import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  BookOpen,
  Building2,
  ClipboardCheck,
  FileSearch,
  FolderKanban,
  DownloadCloud,
  KeyRound,
  Layers3,
  MonitorCog,
  Radar,
  Route,
  Settings2,
  ShieldCheck,
  Ticket,
  Workflow,
} from "lucide-react";

export const SUPPORT_HOME_PATH = "/app/tickets";
export const ADMIN_HOME_PATH = "/app/admin/inventory";

export type AppNavItem = {
  description: string;
  icon: LucideIcon;
  label: string;
  section: "admin" | "support";
  to: string;
  permission?: string;
};

export const appNavigation: AppNavItem[] = [
  {
    label: "Тикеты",
    description: "Очередь и карточка тикета",
    icon: Ticket,
    section: "support",
    to: SUPPORT_HOME_PATH,
    permission: "ticket.queue.view",
  },
  {
    label: "Отчеты",
    description: "KPI, сроки ответа и динамика",
    icon: BarChart3,
    section: "support",
    to: "/app/reports",
    permission: "workspace.support.view",
  },
  {
    label: "База знаний",
    description: "Статьи и категории",
    icon: BookOpen,
    section: "support",
    to: "/app/knowledge",
    permission: "workspace.support.view",
  },
  {
    label: "Настройки",
    description: "Политики и интеграции",
    icon: Settings2,
    section: "support",
    to: "/app/settings",
    permission: "settings.view",
  },
  {
    label: "Инвентарь устройств",
    description: "Список устройств и статус",
    icon: MonitorCog,
    section: "admin",
    to: "/app/admin/inventory",
    permission: "admin.inventory.view",
  },
  {
    label: "Реестры",
    description: "Люди, здания, кабинеты и сервисы",
    icon: Building2,
    section: "admin",
    to: "/app/admin/registry",
    permission: "admin.registry.view",
  },
  {
    label: "Карточка устройства",
    description: "Единая device card",
    icon: ShieldCheck,
    section: "admin",
    to: "/app/admin/device",
    permission: "admin.inventory.view",
  },
  {
    label: "Обновления агента",
    description: "Build registry и rollout policy",
    icon: DownloadCloud,
    section: "admin",
    to: "/app/admin/agent-updates",
    permission: "admin.inventory.view",
  },
  {
    label: "Access Control",
    description: "Роли, permissions и видимость",
    icon: KeyRound,
    section: "admin",
    to: "/app/admin/access",
    permission: "admin.access.view",
  },
  {
    label: "Модули",
    description: "ZIP/SDK-модули агента",
    icon: Layers3,
    section: "admin",
    to: "/app/admin/modules",
    permission: "admin.modules.view",
  },
  {
    label: "Возможности",
    description: "Диагностика, провайдеры, evidence",
    icon: Layers3,
    section: "admin",
    to: "/app/admin/capabilities",
    permission: "admin.modules.view",
  },
  {
    label: "Конструктор форм",
    description: "Каталог intake-форм",
    icon: Workflow,
    section: "admin",
    to: "/app/admin/forms",
    permission: "admin.forms.view",
  },
  {
    label: "Студия шаблонов",
    description: "Услуга, вариант, форма, политики и публикация",
    icon: ClipboardCheck,
    section: "admin",
    to: "/app/admin/request-template-studio",
    permission: "admin.forms.view",
  },
  {
    label: "База знаний",
    description: "Пространства, статьи, версии, ACL и deflection",
    icon: BookOpen,
    section: "admin",
    to: "/app/admin/knowledge",
    permission: "admin.forms.view",
  },
  {
    label: "Каталог услуг",
    description: "Услуги, варианты услуги и проверки публикации",
    icon: FolderKanban,
    section: "admin",
    to: "/app/admin/service-catalog",
    permission: "admin.forms.view",
  },
  {
    label: "Проверка политик",
    description: "Шаблоны обращений, SLA, OLA и видимость",
    icon: ClipboardCheck,
    section: "admin",
    to: "/app/admin/policy-health",
    permission: "admin.forms.view",
  },
  {
    label: "Качество",
    description: "CSAT, повторные открытия, QA и улучшения",
    icon: BarChart3,
    section: "admin",
    to: "/app/admin/quality",
    permission: "admin.forms.view",
  },
  {
    label: "Проблемы",
    description: "Кандидаты, RCA, известные ошибки и обходы",
    icon: FileSearch,
    section: "admin",
    to: "/app/admin/problems",
    permission: "admin.forms.view",
  },
  {
    label: "Изменения",
    description: "Риски, согласования, окна, задачи и PIR",
    icon: Workflow,
    section: "admin",
    to: "/app/admin/changes",
    permission: "admin.forms.view",
  },
  {
    label: "Сценарии",
    description: "Диагностика и guided actions поддержки",
    icon: Route,
    section: "admin",
    to: "/app/admin/playbooks",
    permission: "admin.playbooks.view",
  },
  {
    label: "Observer",
    description: "Трассы и деградации",
    icon: Radar,
    section: "admin",
    to: "/app/admin/observer",
    permission: "admin.observer.view",
  },
  {
    label: "Настройки",
    description: "Уведомления и политики",
    icon: Settings2,
    section: "admin",
    to: "/app/admin/settings",
    permission: "settings.view",
  },
];

export function getWorkspaceLabel(pathname: string) {
  return pathname.startsWith("/app/admin") ? "Администрирование" : "Поддержка";
}

export function getSearchPlaceholder(pathname: string) {
  if (pathname.startsWith("/app/admin")) {
    return "Поиск по устройствам, модулям и трассам";
  }

  if (pathname.startsWith("/app/knowledge")) {
    return "Поиск по статьям и категориям";
  }

  return "Поиск по тикетам, клиентам и тегам";
}

export function isAdminRoute(pathname: string) {
  return pathname.startsWith("/app/admin");
}
