import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronDown, ClipboardCheck, Play, Plus, Settings2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import type { RequestStudioItem, RequestStudioMode, StudioLinks } from "./studio-model";

type DraftStatus = "saved" | "dirty" | "draft_saved" | "validation_required";

export function RequestStudioShell({
  children,
  selectedItem,
  mode,
  modeLabel,
  draftStatus,
  publishHref,
  expertLinks,
  saveDraftDisabled,
  saveDraftPending,
  runValidationDisabled,
  onCreateRequest,
  onSaveDraft,
  onRunValidation,
  onModeChange,
}: {
  children: ReactNode;
  selectedItem: RequestStudioItem | null;
  mode: RequestStudioMode;
  modeLabel: string;
  draftStatus: DraftStatus;
  publishHref: string;
  expertLinks: StudioLinks;
  saveDraftDisabled: boolean;
  saveDraftPending: boolean;
  runValidationDisabled: boolean;
  onCreateRequest: () => void;
  onSaveDraft: () => void;
  onRunValidation: () => void;
  onModeChange: (mode: RequestStudioMode) => void;
}) {
  const draftLabel: Record<DraftStatus, string> = {
    saved: "Сохранено",
    dirty: "Есть несохранённые изменения",
    draft_saved: "Черновик сохранён",
    validation_required: "Проверка требуется",
  };

  return (
    <section className="workspace-page space-y-5 p-6">
      <header className="workspace-page__header">
        <div className="workspace-page__copy">
          <h1>Студия обращений</h1>
          <p>Настройте тип обращения: форму пользователя, правила обработки, сроки, согласования, закрытие и публикацию.</p>
          {selectedItem ? (
            <p className="mt-1 text-sm text-slate-500">
              Сейчас: {selectedItem.service.public_title || selectedItem.service.code} / {selectedItem.offering?.public_title || "тип не выбран"}
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onCreateRequest} type="button" variant="secondary" leadingIcon={<Plus className="h-4 w-4" />}>
            Создать обращение
          </Button>
          <Button disabled={saveDraftDisabled || saveDraftPending} onClick={onSaveDraft} type="button" variant="secondary">
            {saveDraftPending ? "Сохраняем..." : "Сохранить черновик"}
          </Button>
          <Button disabled={runValidationDisabled} onClick={onRunValidation} type="button" leadingIcon={<Play className="h-4 w-4" />}>
            Запустить проверку
          </Button>
          <Link className="inline-flex h-11 items-center justify-center rounded-pill bg-brand-600 px-4 text-sm font-semibold text-white hover:bg-brand-700" to={publishHref}>
            Открыть экспертную публикацию
          </Link>
          <details className="relative">
            <summary className="inline-flex h-11 cursor-pointer list-none items-center justify-center gap-2 rounded-pill border border-border bg-white px-4 text-sm font-semibold text-slate-700 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800">
              <Settings2 className="h-4 w-4" />
              Экспертные инструменты
              <ChevronDown className="h-4 w-4" />
            </summary>
            <div className="absolute right-0 z-20 mt-2 w-64 rounded-md border border-slate-200 bg-white p-2 shadow-xl">
              <ExpertMenuLink href={expertLinks.serviceCatalog} label="Полный каталог услуг" />
              <ExpertMenuLink href={expertLinks.forms} label="Полный конструктор форм" />
              <ExpertMenuLink href={expertLinks.policyHealth} label="Проверка политик" />
            </div>
          </details>
        </div>
      </header>

      <section className="surface-panel flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <p className="text-sm font-semibold text-slate-950">Уровень сложности: {modeLabel}</p>
          <p className="text-xs text-slate-500">Базовый режим скрывает raw JSON, policy refs и внутренние идентификаторы.</p>
          <p className="mt-1 text-xs font-semibold text-brand-800">{draftLabel[draftStatus]}</p>
          <p className="mt-1 text-xs text-slate-500">Публикация через Studio пока недоступна: нет safe publish contract.</p>
        </div>
        <div className="inline-flex rounded-md border border-slate-200 bg-white p-1">
          {(["basic", "advanced", "expert"] as const).map((value) => (
            <button
              className={`rounded px-3 py-1.5 text-sm font-semibold ${mode === value ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-50"}`}
              key={value}
              onClick={() => onModeChange(value)}
              type="button"
            >
              {value === "basic" ? "Базовый" : value === "advanced" ? "Расширенный" : "Экспертный"}
            </button>
          ))}
        </div>
      </section>

      <section className="surface-panel p-4">
        <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
          <ClipboardCheck className="h-4 w-4 text-brand-700" />
          <span>Выберите тип обращения или создайте новый. Настройте форму, маршрут, сроки, согласование, закрытие, уведомления, затем сохраните черновик и запустите проверку.</span>
        </div>
      </section>

      {children}
    </section>
  );
}

function ExpertMenuLink({ href, label }: { href: string; label: string }) {
  return (
    <Link className="block rounded px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-brand-50 hover:text-brand-800" to={href}>
      {label}
    </Link>
  );
}
